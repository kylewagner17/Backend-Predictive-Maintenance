from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models, schemas
from app.device_storage import (
    DevicePredictionRow,
    archive_old_readings_batch,
    ensure_device_tables,
    insert_prediction,
    insert_reading,
    select_predictions,
    select_readings,
)


class SensorReadingPublic:
    __slots__ = ("id", "device_id", "reading", "status", "timestamp")

    def __init__(
        self,
        id: int,
        device_id: int,
        reading: float,
        status: str,
        timestamp: datetime,
    ):
        self.id = id
        self.device_id = device_id
        self.reading = reading
        self.status = status
        self.timestamp = timestamp


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_device(db: Session, device: schemas.DeviceCreate):
    db_device = models.Device(name=device.name)
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    ensure_device_tables(db.get_bind(), db_device.id)
    return db_device


def create_sensor_reading(db: Session, reading: schemas.SensorReadingCreate) -> SensorReadingPublic:
    if reading.recorded_at is None:
        recorded_at = datetime.now(timezone.utc)
    else:
        recorded_at = _as_utc(reading.recorded_at)

    ensure_device_tables(db.get_bind(), reading.device_id)
    rid = insert_reading(
        db,
        reading.device_id,
        reading=reading.reading,
        row_status=reading.status,
        recorded_at=recorded_at,
    )
    db.commit()
    return SensorReadingPublic(
        rid,
        reading.device_id,
        reading.reading,
        reading.status,
        recorded_at,
    )


def get_devices(db: Session):
    return db.query(models.Device).all()


def get_device_by_id(db: Session, device_id: int):
    return db.query(models.Device).filter(models.Device.id == device_id).first()


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
    return db.query(models.PLCTagMap).all()


def create_maintenance_prediction(
    db: Session, prediction: schemas.MaintenancePredictionCreate
) -> DevicePredictionRow:
    data = prediction.model_dump()
    device_id = data["device_id"]
    ensure_device_tables(db.get_bind(), device_id)
    predicted_at = datetime.now(timezone.utc)
    rid = insert_prediction(
        db,
        device_id,
        predicted_at=predicted_at,
        recommendation=data["recommendation"],
        confidence=data.get("confidence"),
        details=data.get("details"),
        readings_snapshot=data.get("readings_snapshot"),
    )
    db.commit()
    return DevicePredictionRow(
        rid,
        device_id,
        predicted_at,
        data["recommendation"],
        data.get("confidence"),
        data.get("details"),
        data.get("readings_snapshot"),
    )


def get_predictions_for_device(db: Session, device_id: int, limit: int = 100):
    ensure_device_tables(db.get_bind(), device_id)
    return select_predictions(db, device_id, limit=limit)


def get_readings_for_device(db: Session, device_id: int, limit: int = 1000):
    ensure_device_tables(db.get_bind(), device_id)
    rows = select_readings(db, device_id, limit=limit)
    return [
        SensorReadingPublic(r.id, device_id, r.reading, r.status, r.timestamp)
        for r in rows
    ]


def update_device_status_field(db: Session, device_id: int, status: str) -> None:
    dev = db.query(models.Device).filter(models.Device.id == device_id).first()
    if dev:
        dev.status = status
        dev.status_updated_at = datetime.now(timezone.utc)
        db.commit()


def create_status_tag_map(db: Session, mapping: schemas.StatusTagMapCreate):
    existing = (
        db.query(models.PLCStatusTagMap)
        .filter(models.PLCStatusTagMap.tag_name == mapping.tag_name)
        .first()
    )
    if existing:
        existing.device_id = mapping.device_id
        db.commit()
        db.refresh(existing)
        return existing
    row = models.PLCStatusTagMap(**mapping.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_status_tag_map_for_device(db: Session, device_id: int):
    return (
        db.query(models.PLCStatusTagMap)
        .filter(models.PLCStatusTagMap.device_id == device_id)
        .first()
    )


def get_all_status_tag_mappings(db: Session):
    return db.query(models.PLCStatusTagMap).all()


def archive_sensor_readings_older_than(
    db: Session,
    *,
    older_than_days: int,
    batch_size: int = 2000,
) -> int:
    """Archive up to ``batch_size`` rows total across devices (oldest first per device)."""
    if older_than_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    bind = db.get_bind()
    device_ids = [row.id for row in db.query(models.Device.id).all()]
    total_moved = 0
    remaining = batch_size
    for device_id in device_ids:
        if remaining <= 0:
            break
        ensure_device_tables(bind, device_id)
        moved = archive_old_readings_batch(
            db, device_id, cutoff=cutoff, batch_size=remaining
        )
        total_moved += moved
        remaining -= moved
    db.commit()
    return total_moved


def get_latest_two_predictions_for_device(db: Session, device_id: int):
    ensure_device_tables(db.get_bind(), device_id)
    rows = select_predictions(db, device_id, limit=2)
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
