"""PostgreSQL OTP service V1: transactions, keyed hashes and sliding limits.

No codes, email addresses, cookies or IP addresses are persisted or logged.
Network delivery happens outside database transactions. A pending reservation
is activated only after confirmed delivery; an older active code survives failure.
"""

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import uuid

import psycopg


@dataclass(frozen=True)
class Result:
    status: str
    challenge_id: str = ""
    retry_after: int = 0


class OTPAuth:
    def __init__(self, database_url, key, authorized_email):
        if not database_url or len(key.encode()) < 32 or not authorized_email:
            raise ValueError(
                "OTP requires DATABASE_URL, OTP_HMAC_KEY (32+ bytes) and AUTHORIZED_EMAIL"
            )
        self.database_url = database_url
        self.key = key.encode()
        self.email = authorized_email.strip().lower()

    def connect(self):
        return psycopg.connect(self.database_url, connect_timeout=5)

    def initialize(self):
        with self.connect() as conn:
            # Serialize DDL when several workers start simultaneously.
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s)", (self.lock_id("otp-schema-v1"),)
            )
            conn.execute(Path(__file__).with_name("otp_schema.sql").read_text())

    def digest(self, purpose, *values):
        # Length-prefixed fields avoid ambiguous concatenation.
        message = purpose + "".join(f"|{len(v)}:{v}" for v in values)
        return hmac.new(self.key, message.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def lock_id(scope):
        return int.from_bytes(
            hashlib.sha256(scope.encode()).digest()[:8], "big", signed=True
        )

    def lock(self, conn, scopes):
        for scope in sorted(set(scopes)):
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (self.lock_id(scope),))

    @staticmethod
    def now(conn):
        # Read after acquiring locks: waiting must not extend code lifetime.
        return conn.execute("SELECT clock_timestamp()").fetchone()[0]

    @staticmethod
    def event(conn, event, subject, client, challenge=None):
        conn.execute(
            "INSERT INTO auth_events(event,subject_hash,client_hash,challenge_id) VALUES (%s,%s,%s,%s)",
            (event, subject, client, challenge),
        )

    def limit(self, conn, scope, now, count, seconds, cooldown=0):
        times = conn.execute(
            "SELECT occurred_at FROM auth_rate_events WHERE scope=%s AND occurred_at>%s ORDER BY occurred_at",
            (scope, now - timedelta(seconds=seconds)),
        ).fetchall()
        delay = 0
        if len(times) >= count:
            delay = max(
                1,
                int(
                    (
                        times[-count][0] + timedelta(seconds=seconds) - now
                    ).total_seconds()
                )
                + 1,
            )
        if times and cooldown:
            delay = max(
                delay,
                int((times[-1][0] + timedelta(seconds=cooldown) - now).total_seconds())
                + 1,
            )
        return max(0, delay)

    @staticmethod
    def hit(conn, scope, now):
        conn.execute(
            "INSERT INTO auth_rate_events(scope,occurred_at) VALUES (%s,%s)",
            (scope, now),
        )

    def request(self, email, browser, client, sender):
        email = email.strip().lower()
        subject = self.digest("subject", email)
        browser_hash = self.digest("browser", browser)
        client_hash = self.digest("client", client)
        ip_scope = "send-ip:" + client_hash
        account_scope = "send-account:" + subject
        browser_scope = "browser:" + browser_hash
        challenge = str(uuid.uuid4())
        code = f"{secrets.randbelow(1_000_000):06d}"
        with self.connect() as conn:
            self.lock(conn, [ip_scope, account_scope, browser_scope])
            now = self.now(conn)
            delay = self.limit(conn, ip_scope, now, 30, 60)
            if delay:
                self.event(conn, "request_limited", subject, client_hash)
                return Result("limited", retry_after=delay)
            self.hit(conn, ip_scope, now)
            if email != self.email:
                self.event(conn, "request_unauthorized", subject, client_hash)
                return Result("unauthorized")
            delay = self.limit(conn, account_scope, now, 5, 900, cooldown=60)
            if delay:
                self.event(conn, "request_limited", subject, client_hash)
                return Result("limited", retry_after=delay)
            self.hit(conn, account_scope, now)
            # A newer reservation supersedes delayed delivery from an older one.
            conn.execute(
                "UPDATE auth_otp_challenges SET state='invalidated' WHERE browser_hash=%s AND state='pending'",
                (browser_hash,),
            )
            conn.execute(
                "INSERT INTO auth_otp_challenges(id,subject_hash,browser_hash,code_hash,created_at,expires_at,state) VALUES (%s,%s,%s,%s,%s,%s,'pending')",
                (
                    challenge,
                    subject,
                    browser_hash,
                    self.digest("otp", challenge, subject, code),
                    now,
                    now + timedelta(seconds=600),
                ),
            )
            self.event(conn, "request_reserved", subject, client_hash, challenge)
        # Never log sender exception text: provider errors can contain the payload.
        try:
            delivery = sender(email, code)
            if not isinstance(delivery, dict) or not delivery.get("id"):
                raise RuntimeError("Delivery not confirmed")
        except Exception:
            with self.connect() as conn:
                self.lock(conn, [browser_scope])
                conn.execute(
                    "UPDATE auth_otp_challenges SET state='failed' WHERE id=%s AND state='pending'",
                    (challenge,),
                )
                self.event(conn, "delivery_failed", subject, client_hash, challenge)
            return Result("delivery_failed")
        finally:
            code = None
        with self.connect() as conn:
            self.lock(conn, [browser_scope])
            now = self.now(conn)
            row = conn.execute(
                "SELECT state,expires_at FROM auth_otp_challenges WHERE id=%s FOR UPDATE",
                (challenge,),
            ).fetchone()
            if row[0] != "pending" or row[1] <= now:
                conn.execute(
                    "UPDATE auth_otp_challenges SET state='expired' WHERE id=%s AND state='pending'",
                    (challenge,),
                )
                self.event(conn, "delivery_stale", subject, client_hash, challenge)
                return Result("delivery_failed")
            conn.execute(
                "UPDATE auth_otp_challenges SET state='invalidated' WHERE browser_hash=%s AND state='active'",
                (browser_hash,),
            )
            conn.execute(
                "UPDATE auth_otp_challenges SET state='active' WHERE id=%s",
                (challenge,),
            )
            self.event(conn, "delivery_confirmed", subject, client_hash, challenge)
        return Result("sent", challenge)

    def verify(self, email, challenge, code, browser, client):
        email = email.strip().lower()
        subject = self.digest("subject", email)
        browser_hash = self.digest("browser", browser)
        client_hash = self.digest("client", client)
        ip_scope = "verify-ip:" + client_hash
        browser_scope = "browser:" + browser_hash
        attempt_scope = "verify-browser:" + browser_hash
        try:
            challenge = str(uuid.UUID(challenge))
        except (ValueError, AttributeError):
            challenge = None
        with self.connect() as conn:
            self.lock(conn, [ip_scope, browser_scope, attempt_scope])
            now = self.now(conn)
            delay = max(
                self.limit(conn, ip_scope, now, 30, 300),
                self.limit(conn, attempt_scope, now, 10, 900),
            )
            if delay:
                self.event(conn, "verification_limited", subject, client_hash)
                return Result("limited", retry_after=delay)
            self.hit(conn, ip_scope, now)
            self.hit(conn, attempt_scope, now)
            row = (
                conn.execute(
                    "SELECT code_hash,expires_at,attempts,state FROM auth_otp_challenges WHERE id=%s AND subject_hash=%s AND browser_hash=%s FOR UPDATE",
                    (challenge, subject, browser_hash),
                ).fetchone()
                if challenge
                else None
            )
            if email != self.email or not row or row[3] != "active":
                self.event(conn, "verification_rejected", subject, client_hash)
                return Result("invalid")
            if row[1] <= now:
                conn.execute(
                    "UPDATE auth_otp_challenges SET state='expired' WHERE id=%s",
                    (challenge,),
                )
                self.event(
                    conn, "verification_expired", subject, client_hash, challenge
                )
                return Result("invalid")
            attempts = row[2] + 1
            correct = bool(re.fullmatch(r"[0-9]{6}", code)) and hmac.compare_digest(
                row[0], self.digest("otp", challenge, subject, code)
            )
            state = "used" if correct else ("exhausted" if attempts >= 5 else "active")
            conn.execute(
                "UPDATE auth_otp_challenges SET attempts=%s,state=%s WHERE id=%s",
                (attempts, state, challenge),
            )
            self.event(
                conn,
                "verification_success" if correct else "verification_failed",
                subject,
                client_hash,
                challenge,
            )
            return Result("verified" if correct else "invalid")
