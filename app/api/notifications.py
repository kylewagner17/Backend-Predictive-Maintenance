"""
Register for notifications when recommendation status changes: push (FCM/APNs) or email (SMTP).
"""
from app import crud, schemas
from app.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/subscribe", response_model=schemas.PushSubscriptionResponse)
def subscribe_push(
    payload: schemas.PushSubscriptionCreate,
    db: Session = Depends(get_db),
):
    """
    Register a push token. Called by the mobile app after obtaining FCM/APNs token.
    - token: the device push token
    - device_id: optional; if set, only notify for this device; if null, notify for all devices
    - platform: optional "ios" | "android" for provider selection
    Same token re-registers (updates device_id/platform).
    """
    return crud.create_push_subscription(db, payload)


@router.post("/subscribe-email", response_model=schemas.EmailSubscriptionResponse)
def subscribe_email(
    payload: schemas.EmailSubscriptionCreate,
    db: Session = Depends(get_db),
):
    """
    Register an email address to receive notifications when recommendation status changes.
    - email: address to send to
    - device_id: optional; if set, only this device; if null, all devices
    Duplicate (email, device_id) is idempotent (returns existing).
    """
    return crud.create_email_subscription(db, payload)
