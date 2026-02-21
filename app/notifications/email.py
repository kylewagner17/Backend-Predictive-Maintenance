"""
Send email via SMTP when recommendation status changes.

Configure SMTP in .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM.
Works with Gmail (use an app password), SendGrid, Mailgun, or any SMTP server.
If SMTP_HOST is empty, emails are logged only and not sent.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send a single email via SMTP (STARTTLS on port 587 by default).

    Returns True if sent successfully, False otherwise.
    If smtp_host is not configured, logs and returns True (no-op).
    """
    if not settings.smtp_host:
        logger.info("Email (SMTP not configured): to=%s subject=%s body=%s", to_email, subject, body)
        return True

    from_addr = settings.mail_from or settings.smtp_user
    if not from_addr:
        logger.warning("Email not sent: MAIL_FROM or SMTP_USER required")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to_email, e)
        return False
