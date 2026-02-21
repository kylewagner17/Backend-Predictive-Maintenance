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


def create_tag_map(db: Session, mapping: schemas.TagMapCreate):
    existing = (
        db.query(models.PLCTagMap)
        .filter(models.PLCTagMap.tag_name == mapping.tag_name)
        .first()
    )

    if existing:
        existing.device_id = mapping.device_id
        db.commit()
        db.refresh(existing)
        return existing
        
    row = models.PLCTagMap(**mapping.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_device_by_tag(db: Session, tag_name: str):
    return (
        db.query(models.PLCTagMap)
        .filter(models.PLCTagMap.tag_name == tag_name)
        .first()
    )


def get_all_tag_mappings(db: Session):
    """All tag_name -> device_id mappings for PLC ingest."""
    return db.query(models.PLCTagMap).all()


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


def get_latest_two_predictions_for_device(db: Session, device_id: int):
    """Returns (latest, previous) prediction or (latest, None) if only one exists."""
    rows = (
        db.query(models.MaintenancePrediction)
        .filter(models.MaintenancePrediction.device_id == device_id)
        .order_by(models.MaintenancePrediction.predicted_at.desc())
        .limit(2)
        .all()
    )
    if not rows:
        return None, None
    if len(rows) == 1:
        return rows[0], None
    return rows[0], rows[1]


def create_push_subscription(db: Session, sub: schemas.PushSubscriptionCreate):
    existing = db.query(models.PushSubscription).filter(models.PushSubscription.token == sub.token).first()
    if existing:
        existing.device_id = sub.device_id
        existing.platform = sub.platform
        db.commit()
        db.refresh(existing)
        return existing
    row = models.PushSubscription(**sub.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_push_subscriptions_for_device(db: Session, device_id: int):
    """Subscriptions that care about this device: device_id match or global (device_id is None)."""
    return (
        db.query(models.PushSubscription)
        .filter(
            (models.PushSubscription.device_id == device_id)
            | (models.PushSubscription.device_id.is_(None))
        )
        .all()
    )


def create_email_subscription(db: Session, sub: schemas.EmailSubscriptionCreate):
    existing = (
        db.query(models.EmailSubscription)
        .filter(
            models.EmailSubscription.email == sub.email,
            models.EmailSubscription.device_id == sub.device_id,
        )
        .first()
    )
    if existing:
        return existing
    row = models.EmailSubscription(**sub.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_email_subscriptions_for_device(db: Session, device_id: int):
    """Emails that care about this device: device_id match or global (device_id is None)."""
    return (
        db.query(models.EmailSubscription)
        .filter(
            (models.EmailSubscription.device_id == device_id)
            | (models.EmailSubscription.device_id.is_(None))
        )
        .all()
    )