"""Write PM recommendation codes to CompactLogix DINT tags (see RECOMMENDATION_TO_DINT)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app import crud
from app.config import settings
from app.ingest.plc_connection import logix_driver_session
from app.industrial.retry import retry_with_backoff

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

RECOMMENDATION_TO_DINT = {
    "OK": 0,
    "INSPECT_SOON": 1,
    "MAINTENANCE_REQUIRED": 2,
}


def push_maintenance_status_to_plc(db: "Session", device_id_to_recommendation: dict[int, str]) -> None:
    if settings.testing or not settings.plc_status_write_enabled:
        logger.debug("PLC status write skipped (testing=%s enabled=%s)", settings.testing, settings.plc_status_write_enabled)
        return
    if not device_id_to_recommendation:
        return

    mappings = crud.get_all_status_tag_mappings(db)
    if not mappings:
        logger.debug("PLC status write skipped (no plc_status_tag_map rows)")
        return

    writes: list[tuple[str, int]] = []
    for m in mappings:
        rec = device_id_to_recommendation.get(m.device_id)
        if rec is None:
            continue
        code = RECOMMENDATION_TO_DINT.get(rec)
        if code is None:
            logger.warning("Unknown recommendation %r for device_id=%s; skipping PLC write", rec, m.device_id)
            continue
        writes.append((m.tag_name, code))

    if not writes:
        return

    def _write() -> None:
        with logix_driver_session() as plc:
            plc.write(*writes)

    try:
        retry_with_backoff(
            _write,
            attempts=max(1, settings.plc_retry_attempts),
            base_delay_sec=settings.plc_retry_base_delay_seconds,
            operation_name="PLC status tag write",
        )
        logger.info(
            "PLC status write OK: %s tag(s) on %s",
            len(writes),
            settings.plc_host,
        )
    except Exception as e:
        logger.error("PLC status write failed after retries: %s", e)
