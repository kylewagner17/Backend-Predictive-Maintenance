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


_OP300_OUTPUT_ORDER = ("Valves_Good", "Inspection_Needed", "Maintenance")


def push_op300_outputs_to_plc(
    db: "Session",
    *,
    output_device_id: int,
    valves_good: int,
    inspection_needed: int,
    maintenance: int,
) -> None:
    """Write 0/1 DINT/Bool-style values to the three mapped controller tags for OP300_Outputs."""
    if settings.testing or not settings.plc_status_write_enabled:
        logger.debug(
            "PLC OP300 outputs skipped (testing=%s enabled=%s)",
            settings.testing,
            settings.plc_status_write_enabled,
        )
        return

    vals = {
        "Valves_Good": int(bool(valves_good)),
        "Inspection_Needed": int(bool(inspection_needed)),
        "Maintenance": int(bool(maintenance)),
    }
    mappings = [
        m for m in crud.get_all_status_tag_mappings(db) if m.device_id == output_device_id
    ]
    writes: list[tuple[str, int]] = []
    for name in _OP300_OUTPUT_ORDER:
        v = vals[name]
        row = next((m for m in mappings if m.tag_name == name), None)
        if row is None:
            logger.warning("PLC OP300 skip: no plc_status_tag_map row for tag %r", name)
            continue
        writes.append((row.tag_name, v))

    if not writes:
        logger.debug("PLC OP300 write skipped (no mapped tags)")
        return

    def _write() -> None:
        with logix_driver_session() as plc:
            plc.write(*writes)

    try:
        retry_with_backoff(
            _write,
            attempts=max(1, settings.plc_retry_attempts),
            base_delay_sec=settings.plc_retry_base_delay_seconds,
            operation_name="PLC OP300 tag write",
        )
        logger.info(
            "PLC OP300 write OK: %s on %s",
            vals,
            settings.plc_host,
        )
    except Exception as e:
        logger.error("PLC OP300 write failed after retries: %s", e)
