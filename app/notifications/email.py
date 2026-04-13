"""SMTP mail (STARTTLS on 587 by default). Set SMTP_* and MAIL_FROM in .env."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
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
