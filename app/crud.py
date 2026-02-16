from sqlalchemy.orm import Session
from app import models, schemas

def create_device(db: Session, device: schemas.DeviceCreate):
    db_device = models.Device(name=device.name)
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device


def create_sensor_reading(db: Session, reading: schemas.SensorReadingCreate):
    db_reading = models.SensorReading(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


def get_devices(db: Session):
    return db.query(models.Device).all()


def create_register_map(db: Session, mapping: schemas.RegisterMapCreate):
    db_map = models.PLCRegisterMap(
        register_address=mapping.register_address,
        device_id=mapping.device_id
    )
    db.add(db_map)
    db.commit()
    return db_map

    
def get_device_by_register(db: Session, register_address: int):
    return (
        db.query(models.PLCRegisterMap)
        .filter(models.PLCRegisterMap.register_address == register_address)
        .first()
    )


def create_maintenance_prediction(db: Session, prediction: schemas.MaintenancePredictionCreate):
    row = models.MaintenancePrediction(**prediction.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_predictions_for_device(db: Session, device_id: int, limit: int = 100):
    return (
        db.query(models.MaintenancePrediction)
        .filter(models.MaintenancePrediction.device_id == device_id)
        .order_by(models.MaintenancePrediction.predicted_at.desc())
        .limit(limit)
        .all()
    )


def get_readings_for_device(db: Session, device_id: int, limit: int = 1000):
    return (
        db.query(models.SensorReading)
        .filter(models.SensorReading.device_id == device_id)
        .order_by(models.SensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )