from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass

from app.config import settings


@dataclass
class OtpRecord:
    code_hash: str
    expires_at: int
    attempts: int
    requested_at: int


_LOCK = threading.Lock()
_OTP_STORE: dict[str, OtpRecord] = {}


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _otp_hash(email: str, code: str) -> str:
    payload = f"{normalize_email(email)}:{code}".encode("utf-8")
    return hmac.new(settings.session_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def issue_otp(email: str) -> tuple[str, int]:
    normalized = normalize_email(email)
    now = int(time.time())

    with _LOCK:
        existing = _OTP_STORE.get(normalized)
        if existing and now - existing.requested_at < settings.otp_request_cooldown_seconds:
            remaining = settings.otp_request_cooldown_seconds - (now - existing.requested_at)
            raise ValueError(f"Aguarde {remaining} segundo(s) para solicitar um novo código.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = now + settings.otp_ttl_seconds
        _OTP_STORE[normalized] = OtpRecord(
            code_hash=_otp_hash(normalized, code),
            expires_at=expires_at,
            attempts=0,
            requested_at=now,
        )
        return code, expires_at


def verify_otp_code(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    now = int(time.time())

    with _LOCK:
        record = _OTP_STORE.get(normalized)
        if not record:
            return False
        if now > record.expires_at:
            _OTP_STORE.pop(normalized, None)
            return False
        if record.attempts >= settings.otp_max_attempts:
            _OTP_STORE.pop(normalized, None)
            return False

        record.attempts += 1
        supplied = _otp_hash(normalized, code)
        if not hmac.compare_digest(record.code_hash, supplied):
            return False

        _OTP_STORE.pop(normalized, None)
        return True


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(email: str) -> str:
    now = int(time.time())
    payload = {
        "sub": normalize_email(email),
        "iat": now,
        "exp": now + settings.session_ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(
        hmac.new(settings.session_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


def verify_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None

    encoded, supplied_signature = token.split(".", 1)
    expected_signature = _b64url(
        hmac.new(settings.session_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(encoded))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    subject = normalize_email(str(payload.get("sub", "")))
    if subject != normalize_email(settings.authorized_email):
        return None
    return subject
