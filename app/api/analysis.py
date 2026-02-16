from app import crud
from app.analysis.predict import run_predictions_all_devices
from app.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run")
def run_analysis(db: Session = Depends(get_db)):
    """
    Run predictive maintenance analysis for all devices.
    Reads recent sensor data and writes results to maintenance_predictions.
    """
    run_predictions_all_devices(db)
    return {"status": "ok", "message": "Predictions updated for all devices."}
