from app import crud, schemas
from app.database import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=list[schemas.DeviceResponse])
def list_devices(db: Session = Depends(get_db)):
    return crud.get_devices(db)


@router.get("/{device_id}/predictions", response_model=list[schemas.MaintenancePredictionResponse])
def get_device_predictions(
    device_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    return crud.get_predictions_for_device(db, device_id, limit=limit)
