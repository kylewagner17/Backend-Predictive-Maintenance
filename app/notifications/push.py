"""
Notify subscribers when recommendation status changes: push (FCM/APNs) and/or email (SMTP).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.notifications.email import send_email

logger = logging.getLogger(__name__)


def send_push(token: str, title: str, body: str, platform: str | None = None) -> bool:
    """
    Send a push notification to one device token.

    Stub: logs the notification. Replace with real implementation, e.g.:
    - Android: firebase-admin (FCM) or requests to FCM HTTP v1 API
    - iOS: apns2 or PyAPNs2

    Returns True if sent (or queued) successfully, False otherwise.
    """
    if not getattr(settings, "notifications_enabled", True):
        logger.debug("Notifications disabled; would send to %s: %s - %s", token[:20], title, body)
        return True

    # Stub: log only. Replace with FCM/APNs call.
    logger.info("PUSH [%s] %s: %s (token=%s...)", platform or "?", title, body, token[:24] if len(token) > 24 else token)
    return True


def notify_subscribers_on_recommendation_change(
    db: Session,
    device_id: int,
    device_name: str,
    old_recommendation: str | None,
    new_recommendation: str,
) -> None:
    """
    If recommendation changed, notify push and email subscribers for this device.
    """
    if old_recommendation == new_recommendation:
        return

    title = "Maintenance status changed"
    body = f"{device_name}: {old_recommendation or 'N/A'} → {new_recommendation}"

    # Push (stub until FCM/APNs implemented)
    if getattr(settings, "notifications_enabled", True):
        for sub in crud.get_push_subscriptions_for_device(db, device_id):
            try:
                send_push(sub.token, title, body, sub.platform)
            except Exception as e:
                logger.exception("Failed to send push to subscription %s: %s", sub.id, e)

    # Email (SMTP when configured)
    for sub in crud.get_email_subscriptions_for_device(db, device_id):
        try:
            send_email(sub.email, title, body)
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", sub.email, e)
