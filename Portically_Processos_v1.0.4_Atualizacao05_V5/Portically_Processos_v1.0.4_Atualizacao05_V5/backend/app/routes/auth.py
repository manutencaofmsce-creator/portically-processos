from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.core.auth_security import (
    create_session_token,
    issue_otp,
    normalize_email,
    verify_otp_code,
    verify_session_token,
)
from app.services.audit import audit_event
from app.services.otp_sender import send_otp

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RequestOtpBody(BaseModel):
    email: EmailStr


class VerifyOtpBody(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


def _is_authorized(email: str) -> bool:
    return normalize_email(email) == normalize_email(settings.authorized_email)


@router.post("/request-otp")
def request_otp(payload: RequestOtpBody, request: Request):
    normalized = normalize_email(payload.email)

    if not _is_authorized(normalized):
        audit_event("auth.otp.request", "denied", email=normalized)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado para este e-mail.",
        )

    if settings.otp_provider == "not_configured":
        audit_event("auth.otp.request", "provider_not_configured", email=normalized)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O envio de código ainda não foi configurado no servidor.",
        )

    try:
        code, _ = issue_otp(normalized)
        send_otp(normalized, code)
    except ValueError as exc:
        audit_event("auth.otp.request", "rate_limited", email=normalized)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except RuntimeError as exc:
        audit_event("auth.otp.request", "delivery_failed", email=normalized)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    audit_event("auth.otp.request", "sent", email=normalized)
    return {"message": "Código de acesso enviado."}


@router.post("/verify-otp")
def verify_otp(payload: VerifyOtpBody, response: Response):
    normalized = normalize_email(payload.email)

    if not _is_authorized(normalized):
        audit_event("auth.otp.verify", "denied", email=normalized)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso não autorizado.")

    if not verify_otp_code(normalized, payload.code):
        audit_event("auth.otp.verify", "invalid", email=normalized)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido, expirado ou já utilizado.",
        )

    token = create_session_token(normalized)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    audit_event("auth.login", "success", email=normalized)
    return {"message": "Acesso autorizado."}


@router.get("/session")
def session(request: Request):
    email = verify_session_token(request.cookies.get(settings.session_cookie_name))
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.")
    return {"authenticated": True, "email": email}


@router.post("/logout")
def logout(request: Request, response: Response):
    email = verify_session_token(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    audit_event("auth.logout", "success", email=email or "unknown")
    return {"message": "Sessão encerrada."}
