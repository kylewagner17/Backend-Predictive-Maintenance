from app import crud, schemas
from app.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/sensors", tags=["sensors"])

@router.post("/reading", response_model=schemas.SensorReadingResponse)
def ingest_reading(
    reading: schemas.SensorReadingCreate, 
    db: Session = Depends(get_db)
):
    return crud.create_sensor_reading(db, reading)