"""
Predictive maintenance analysis stub.

Flow: query recent sensor_readings per device -> run logic -> write to maintenance_predictions.

Possible implementations:
- Threshold: flag MAINTENANCE_REQUIRED if reading exceeds a limit or trend slope.
- Rolling stats: mean/std over a window; flag if current reading is N sigma away.
- Time-series model: simple regression or LSTM to predict failure window.
- External ML: call a trained model (e.g. scikit-learn, TensorFlow) on features from readings.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import crud, schemas


def run_predictions_for_device(db: Session, device_id: int) -> None:
    """
    Run prediction logic for one device and persist result.

    Replace this with real logic: load readings, compute features, call model,
    then crud.create_maintenance_prediction(db, schemas.MaintenancePredictionCreate(...)).
    """
    readings = crud.get_readings_for_device(db, device_id, limit=500)
    if not readings:
        return

    #simple threshold example 
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


def run_predictions_all_devices(db: Session) -> None:
    """Run predictions for every device that has register mappings."""
    devices = crud.get_devices(db)
    for d in devices:
        run_predictions_for_device(db, d.id)
