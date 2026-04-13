"""Move aged rows from each ``device_{id}_readings`` table into ``device_{id}_readings_archive``."""

from __future__ import annotations

import logging

from app import crud
from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def run_sensor_readings_retention() -> int:
    """One batch; call repeatedly until it returns 0 if you need to drain a large backlog."""
    db = SessionLocal()
    try:
        total = crud.archive_sensor_readings_older_than(
            db,
            older_than_days=settings.sensor_readings_retention_days,
            batch_size=settings.retention_batch_size,
        )
        if total:
            logger.info("Retention archived %s sensor reading row(s)", total)
        return total
    finally:
        db.close()
