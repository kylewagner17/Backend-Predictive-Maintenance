"""
Notify subscribers when recommendation changes (push stub; email via SMTP).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.notifications.email import send_email

logger = logging.getLogger(__name__)


def send_push(token: str, title: str, body: str, platform: str | None = None) -> bool:
    if not getattr(settings, "notifications_enabled", True):
        logger.debug("Notifications disabled; would send to %s: %s - %s", token[:20], title, body)
        return True

    logger.info("PUSH [%s] %s: %s (token=%s...)", platform or "?", title, body, token[:24] if len(token) > 24 else token)
    return True


def notify_subscribers_on_recommendation_change(
    db: Session,
    device_id: int,
    device_name: str,
    old_recommendation: str | None,
    new_recommendation: str,
) -> None:
    if old_recommendation == new_recommendation:
        return

    title = "Maintenance status changed"
    body = f"{device_name}: {old_recommendation or 'N/A'} -> {new_recommendation}"

    if getattr(settings, "notifications_enabled", True):
        for sub in crud.get_push_subscriptions_for_device(db, device_id):
            try:
                send_push(sub.token, title, body, sub.platform)
            except Exception as e:
                logger.exception("Failed to send push to subscription %s: %s", sub.id, e)

    if not getattr(settings, "notifications_enabled", True):
        return
    if not settings.smtp_host:
        logger.debug("Email skipped (SMTP_HOST not set): %s", body)
        return

    sent_lower: set[str] = set()
    for sub in crud.get_email_subscriptions_for_device(db, device_id):
        try:
            send_email(sub.email, title, body)
            sent_lower.add(sub.email.strip().lower())
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", sub.email, e)

    extra = (settings.notification_alert_email or "").strip()
    if extra and extra.lower() not in sent_lower:
        try:
            send_email(extra, title, body)
        except Exception as e:
            logger.exception("Failed to send alert email to %s: %s", extra, e)
