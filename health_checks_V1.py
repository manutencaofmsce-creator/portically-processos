"""Read-only, bounded probes. Public responses never contain dependency details."""
import psycopg
from cryptography.fernet import Fernet
from fastapi.responses import JSONResponse


BASE_TABLES = ("radar_items", "audit_log")
PROCESS_TABLES = ("process_records", "process_documents", "process_validations")
OTP_TABLES = ("auth_otp_challenges", "auth_rate_events", "auth_events")
CONNECT_TIMEOUT_SECONDS = 3
STATEMENT_TIMEOUT_MS = 1000


def is_ready(settings):
    """Use the deployed app's namespace, including additive V21/V22 features.

    No startup/migrations, writes, counts, OTP delivery, or case reads occur here.
    """
    required = ("DATABASE_URL", "DATA_ENCRYPTION_KEY", "DATA_HMAC_KEY",
                "AUTHORIZED_EMAIL", "SESSION_SECRET", "RESEND_API_KEY", "RESEND_FROM_EMAIL")
    try:
        if any(not str(settings.get(key, "")).strip() for key in required):
            return False
        key = settings["DATA_ENCRYPTION_KEY"].strip()
        key += "=" * ((4 - len(key) % 4) % 4)
        Fernet(key.encode())
        tables = list(BASE_TABLES)
        if "NEW_CASE" in settings:
            tables.extend(PROCESS_TABLES)
        if "otp_service" in settings:
            if len(settings.get("OTP_HMAC_KEY", "").encode()) < 32:
                return False
            if len(settings["SESSION_SECRET"].encode()) < 32:
                return False
            tables.extend(OTP_TABLES)
        if "CaseStore" in settings:
            tables.append("protected_case_bundles")
        # Explicit arguments override connection-string options. Synchronous routes
        # run in FastAPI's threadpool; /health does not share this dependency.
        with psycopg.connect(settings["DATABASE_URL"], connect_timeout=CONNECT_TIMEOUT_SECONDS,
                             options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c default_transaction_read_only=on") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                if cur.fetchone() != (1,):
                    return False
                for table in tables:
                    # Fixed internal identifiers only; validates table visibility and
                    # SELECT permission without retrieving any records.
                    cur.execute(f'SELECT * FROM public."{table}" LIMIT 0')
        return True
    except Exception:
        # Never return/log exception text, URLs, credentials, rows, or SQL details.
        return False


def readiness_response(settings):
    ready = is_ready(settings)
    return JSONResponse({"status": "ready" if ready else "not-ready"},
                        status_code=200 if ready else 503,
                        headers={"Cache-Control": "no-store, max-age=0"})
