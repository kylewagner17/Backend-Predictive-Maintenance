"""
Per-device tables: ``device_{id}_readings``, ``device_{id}_predictions``,
``device_{id}_readings_archive``. ``devices`` holds current PM status and ``status_updated_at``.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Table, delete, func, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app import models
from app.database import Base


def readings_table_name(device_id: int) -> str:
    return f"device_{device_id}_readings"


def predictions_table_name(device_id: int) -> str:
    return f"device_{device_id}_predictions"


def readings_archive_table_name(device_id: int) -> str:
    return f"device_{device_id}_readings_archive"


def _readings_table(device_id: int) -> Table:
    name = readings_table_name(device_id)
    if name in Base.metadata.tables:
        return Base.metadata.tables[name]
    return Table(
        name,
        Base.metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("reading", Float, nullable=False),
        Column("row_status", String, nullable=False),
        Column("recorded_at", DateTime(timezone=True), nullable=False),
    )


def _predictions_table(device_id: int) -> Table:
    name = predictions_table_name(device_id)
    if name in Base.metadata.tables:
        return Base.metadata.tables[name]
    return Table(
        name,
        Base.metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("predicted_at", DateTime(timezone=True), nullable=False),
        Column("recommendation", String, nullable=False),
        Column("confidence", Float, nullable=True),
        Column("details", String, nullable=True),
        Column("readings_snapshot", JSON, nullable=True),
    )


def _readings_archive_table(device_id: int) -> Table:
    name = readings_archive_table_name(device_id)
    if name in Base.metadata.tables:
        return Base.metadata.tables[name]
    return Table(
        name,
        Base.metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("reading", Float, nullable=False),
        Column("row_status", String, nullable=False),
        Column("original_recorded_at", DateTime(timezone=True), nullable=False),
        Column("archived_at", DateTime(timezone=True), nullable=False),
    )


def ensure_device_tables(engine: Engine, device_id: int) -> None:
    for builder in (_readings_table, _predictions_table, _readings_archive_table):
        builder(device_id).create(engine, checkfirst=True)


class DeviceReadingRow:
    __slots__ = ("id", "reading", "status", "timestamp")

    def __init__(self, id: int, reading: float, status: str, timestamp: dt.datetime):
        self.id = id
        self.reading = reading
        self.status = status
        self.timestamp = timestamp


class DevicePredictionRow:
    __slots__ = (
        "id",
        "device_id",
        "predicted_at",
        "recommendation",
        "confidence",
        "details",
        "readings_snapshot",
    )

    def __init__(
        self,
        id: int,
        device_id: int,
        predicted_at: dt.datetime,
        recommendation: str,
        confidence: float | None,
        details: str | None,
        readings_snapshot: Any,
    ):
        self.id = id
        self.device_id = device_id
        self.predicted_at = predicted_at
        self.recommendation = recommendation
        self.confidence = confidence
        self.details = details
        self.readings_snapshot = readings_snapshot


def insert_reading(
    db: Session,
    device_id: int,
    *,
    reading: float,
    row_status: str,
    recorded_at: dt.datetime,
) -> int:
    t = _readings_table(device_id)
    stmt = (
        insert(t)
        .values(reading=reading, row_status=row_status, recorded_at=recorded_at)
        .returning(t.c.id)
    )
    return int(db.execute(stmt).scalar_one())


def select_readings(db: Session, device_id: int, *, limit: int) -> list[DeviceReadingRow]:
    t = _readings_table(device_id)
    q = (
        select(t.c.id, t.c.reading, t.c.row_status, t.c.recorded_at)
        .order_by(t.c.recorded_at.desc(), t.c.id.desc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    return [
        DeviceReadingRow(r.id, r.reading, r.row_status, r.recorded_at) for r in rows
    ]


def insert_prediction(
    db: Session,
    device_id: int,
    *,
    predicted_at: dt.datetime,
    recommendation: str,
    confidence: float | None,
    details: str | None,
    readings_snapshot: list[dict[str, Any]] | None,
) -> int:
    t = _predictions_table(device_id)
    stmt = (
        insert(t)
        .values(
            predicted_at=predicted_at,
            recommendation=recommendation,
            confidence=confidence,
            details=details,
            readings_snapshot=readings_snapshot,
        )
        .returning(t.c.id)
    )
    return int(db.execute(stmt).scalar_one())


def select_predictions(db: Session, device_id: int, *, limit: int) -> list[DevicePredictionRow]:
    t = _predictions_table(device_id)
    q = (
        select(
            t.c.id,
            t.c.predicted_at,
            t.c.recommendation,
            t.c.confidence,
            t.c.details,
            t.c.readings_snapshot,
        )
        .order_by(t.c.predicted_at.desc(), t.c.id.desc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    return [
        DevicePredictionRow(
            r.id,
            device_id,
            r.predicted_at,
            r.recommendation,
            r.confidence,
            r.details,
            r.readings_snapshot,
        )
        for r in rows
    ]


def archive_old_readings_batch(
    db: Session,
    device_id: int,
    *,
    cutoff: dt.datetime,
    batch_size: int,
) -> int:
    t_r = _readings_table(device_id)
    t_a = _readings_archive_table(device_id)
    q = (
        select(t_r.c.id, t_r.c.reading, t_r.c.row_status, t_r.c.recorded_at)
        .where(t_r.c.recorded_at < cutoff)
        .order_by(t_r.c.id.asc())
        .limit(batch_size)
    )
    rows = db.execute(q).all()
    if not rows:
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    for r in rows:
        db.execute(
            insert(t_a).values(
                reading=r.reading,
                row_status=r.row_status,
                original_recorded_at=r.recorded_at,
                archived_at=now,
            )
        )
        db.execute(delete(t_r).where(t_r.c.id == r.id))
    return len(rows)


def count_readings(db: Session, device_id: int) -> int:
    t = _readings_table(device_id)
    return int(db.execute(select(func.count()).select_from(t)).scalar_one())


def count_archived_readings(db: Session, device_id: int) -> int:
    t = _readings_archive_table(device_id)
    return int(db.execute(select(func.count()).select_from(t)).scalar_one())


def sync_tables_for_all_devices(db: Session) -> None:
    bind = db.get_bind()
    for d in db.query(models.Device).all():
        ensure_device_tables(bind, d.id)
