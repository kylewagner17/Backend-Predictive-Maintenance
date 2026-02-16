from app import crud, schemas
from app.database import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.post("/reading", response_model=schemas.SensorReadingResponse)
def ingest_reading(
    reading: schemas.SensorReadingCreate,
    db: Session = Depends(get_db),
):
    return crud.create_sensor_reading(db, reading)


@router.get("/readings/{device_id}", response_model=list[schemas.SensorReadingResponse])
def get_readings(
    device_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(1000, ge=1, le=10000),
):
    return crud.get_readings_for_device(db, device_id, limit=limit)