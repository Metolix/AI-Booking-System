from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def _settings() -> tuple[str, str, str, int]:
    email = os.getenv("ZOHO_EMAIL", "").strip()
    password = os.getenv("ZOHO_PASSWORD", "")
    host = os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.com").strip()
    port = int(os.getenv("ZOHO_SMTP_PORT", "465"))
    if not email or not password:
        raise RuntimeError("Email service is not configured.")
    return email, password, host, port


def send_email(*, to: str, subject: str, body: str) -> None:
    sender, password, host, port = _settings()
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


def send_confirmation(*, booking: dict) -> None:
    send_email(
        to=booking["email"],
        subject="(DEMO) Your appointment is confirmed",
        body=(
            "Your appointment has been confirmed. (THIS IS A DEMO)\n\n"
            f"Name: {booking['name']}\n"
            f"Service: {booking['service']}\n"
            f"Start: {booking['start_at']}\n"
            f"End: {booking['end_at']}\n"
            f"Phone: {booking['phone']}\n\n"
            "If you need to change or cancel this appointment, please contact the business."
        ),
    )
