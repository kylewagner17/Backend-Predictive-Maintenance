"""
Predictive maintenance analysis stub.

Flow: query recent sensor_readings per device -> run logic -> write to maintenance_predictions.
When recommendation status changes, push notifications are sent to subscribed tokens.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import crud, schemas
from app.notifications.push import notify_subscribers_on_recommendation_change


def run_predictions_for_device(db: Session, device_id: int) -> None:
    """
    Run prediction logic for one device and persist result.
    If recommendation changed from previous, sends push notifications to subscribers.
    """
    readings = crud.get_readings_for_device(db, device_id, limit=500)
    if not readings:
        return

    # Previous recommendation (before we write the new one) for change detection
    latest_pred, _ = crud.get_latest_two_predictions_for_device(db, device_id)
    old_recommendation = latest_pred.recommendation if latest_pred else None

    # Simple threshold example
    latest = readings[0]
    if latest.reading > 1000:
        recommendation = "MAINTENANCE_REQUIRED"
    elif latest.reading > 500:
        recommendation = "INSPECT_SOON"
    else:
        recommendation = "OK"

    crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(
            device_id=device_id,
            recommendation=recommendation,
            confidence=None,
            details=f"Latest reading: {latest.reading}",
        ),
    )

    # Notify push subscribers when status changes
    device = next((d for d in crud.get_devices(db) if d.id == device_id), None)
    device_name = device.name if device else f"Device {device_id}"
    notify_subscribers_on_recommendation_change(
        db, device_id, device_name, old_recommendation, recommendation
    )


def run_predictions_all_devices(db: Session) -> None:
    """Run predictions for every device that has tag mappings."""
    devices = crud.get_devices(db)
    for d in devices:
        run_predictions_for_device(db, d.id)
