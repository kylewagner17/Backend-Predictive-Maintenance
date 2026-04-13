"""CompactLogix ingest: read mapped tags, persist floats to sensor_readings."""

import logging
import time

from app import crud, schemas
from app.config import settings
from app.database import SessionLocal
from app.ingest.plc_connection import logix_driver_session
from app.industrial.retry import retry_with_backoff

logger = logging.getLogger(__name__)


def _tag_value_to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def poll_plc() -> None:
    db = SessionLocal()
    try:
        mappings = crud.get_all_tag_mappings(db)
        if not mappings:
            logger.info("PLC poll skipped (no tag mappings configured)")
            return

        tag_names = [m.tag_name for m in mappings]

        def _read_tags():
            with logix_driver_session() as plc:
                return plc.read(*tag_names)

        try:
            results = retry_with_backoff(
                _read_tags,
                attempts=max(1, settings.plc_retry_attempts),
                base_delay_sec=settings.plc_retry_base_delay_seconds,
                operation_name="PLC tag read",
            )
        except Exception as e:
            logger.error("PLC connection/read failed after retries: %s", e)
            return

        result_list = (
            results
            if results is not None and isinstance(results, list)
            else ([results] if results is not None else [])
        )

        if not result_list:
            logger.warning("PLC poll: empty response from controller")
            return

        lines: list[str] = []
        saved_count = 0
        for item in result_list:
            tag_name = item.tag

            if item.error:
                lines.append(f"  {tag_name}: error - {item.error}")
                continue

            value = item.value
            type_name = getattr(item, "type", None) or ""
            suffix = f" ({type_name})" if type_name else ""
            line = f"  {tag_name}: {value!r}{suffix}"

            fval = _tag_value_to_float(value)
            if fval is None:
                lines.append(f"{line} -> not saved (non-numeric)")
                continue

            mapping = crud.get_device_by_tag(db, tag_name)
            if not mapping:
                lines.append(f"{line} -> not saved (no device mapping)")
                continue

            reading = schemas.SensorReadingCreate(
                device_id=mapping.device_id,
                reading=fval,
                status="OK",
            )
            crud.create_sensor_reading(db, reading)
            saved_count += 1
            lines.append(f"{line} -> saved as reading {fval}")

        logger.info("PLC poll data read:\n%s", "\n".join(lines))
        if saved_count:
            logger.info("PLC poll: %s sensor reading(s) saved", saved_count)
        else:
            logger.info("PLC poll: no sensor readings saved")

    except Exception as e:
        logger.exception("PLC poll database error: %s", e)

    finally:
        db.close()


def plc_loop() -> None:
    while True:
        try:
            poll_plc()
        except Exception as e:
            logger.exception("PLC loop crashed: %s", e)
        time.sleep(settings.plc_poll_interval_seconds)
