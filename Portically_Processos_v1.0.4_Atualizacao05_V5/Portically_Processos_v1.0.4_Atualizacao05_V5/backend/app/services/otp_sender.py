from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings


def send_otp(email: str, code: str) -> None:
    provider = settings.otp_provider.strip().lower()

    if provider == "console":
        if settings.app_env == "production":
            raise RuntimeError("Provedor console não é permitido em produção.")
        print(f"[DEV OTP] {email}: {code}")
        return

    if provider != "smtp":
        raise RuntimeError("O envio de código ainda não foi configurado no servidor.")

    required = [settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email]
    if not all(required):
        raise RuntimeError("Configuração SMTP incompleta.")

    message = EmailMessage()
    message["Subject"] = "Código de acesso — Portically Processos"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(
        "Seu código de acesso ao Portically Processos é: "
        f"{code}\n\nO código é de uso único e expira em poucos minutos."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
