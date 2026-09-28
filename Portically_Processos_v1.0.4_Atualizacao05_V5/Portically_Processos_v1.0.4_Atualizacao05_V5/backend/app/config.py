from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "1.0.4"
    authorized_email: str
    frontend_origin: str = "http://localhost:3000"

    # OTP
    otp_provider: str = "not_configured"  # not_configured | console | smtp
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    otp_request_cooldown_seconds: int = 60

    # SMTP (used only when otp_provider=smtp)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True

    # Session
    session_secret: str
    session_cookie_name: str = "portically_processos_session"
    session_ttl_seconds: int = 8 * 60 * 60
    session_cookie_secure: bool = True

    # Audit
    audit_log_path: str = "./data/auth_audit.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
