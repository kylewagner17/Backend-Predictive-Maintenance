"""
Allen-Bradley CompactLogix ingestion via pycomm3 (EtherNet/IP).
Reads controller tags and writes values to sensor_readings using plc_tag_map.
"""
import time
from pycomm3 import LogixDriver
from app.config import settings
from app.database import SessionLocal
from app import crud, schemas


def _tag_value_to_float(value) -> float | None:
    """Convert tag value to float; return None if not numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def poll_plc():
    db = SessionLocal()
    try:
        mappings = crud.get_all_tag_mappings(db)
        if not mappings:
            print("PLC poll: skipped (no tag mappings configured).")
            return

        tag_names = [m.tag_name for m in mappings]

        try:
            with LogixDriver(settings.plc_host) as plc:
                results = plc.read(*tag_names)

        except Exception as e:
            print("PLC connection/read error:", e)
            return

        # pycomm3 read() returns list of Tag (tag, value, type, error)
        result_list = (
            results
            if results is not None and isinstance(results, list)
            else ([results] if results is not None else [])
        )

        if not result_list:
            print("PLC poll: no data received (empty response from controller).")
            return

        lines: list[str] = []
        saved_count = 0
        for item in result_list:
            tag_name = item.tag

            if item.error:
                lines.append(f"  {tag_name}: error — {item.error}")
                continue

            value = item.value
            type_name = getattr(item, "type", None) or ""
            suffix = f" ({type_name})" if type_name else ""
            line = f"  {tag_name}: {value!r}{suffix}"

            fval = _tag_value_to_float(value)
            if fval is None:
                lines.append(f"{line} → not saved (non-numeric)")
                continue

            mapping = crud.get_device_by_tag(db, tag_name)
            if not mapping:
                lines.append(f"{line} → not saved (no device mapping)")
                continue

            reading = schemas.SensorReadingCreate(
                device_id=mapping.device_id,
                reading=fval,
                status="OK",
            )
            crud.create_sensor_reading(db, reading)
            saved_count += 1
            lines.append(f"{line} → saved as reading {fval}")

        print("PLC poll — data read:")
        print("\n".join(lines))
        if saved_count:
            print(f"PLC poll: {saved_count} sensor reading(s) saved.")
        else:
            print("PLC poll: no sensor readings saved (errors, unmapped tags, or non-numeric values).")

    except Exception as e:
        print("Database error:", e)

    finally:
        db.close()


def plc_loop():
    while True:
        try:
            poll_plc()
        except Exception as e:
            print("PLC loop crashed:", e)
        time.sleep(settings.plc_poll_interval_seconds)
