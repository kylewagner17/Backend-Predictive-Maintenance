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
            return

        tag_names = [m.tag_name for m in mappings]

        try:
            with LogixDriver(settings.plc_host) as plc:
                results = plc.read(*tag_names)

        except Exception as e:
            print("PLC connection/read error:", e)
            return

        if not results:
            return

        # pycomm3 read() returns list of Tag (tag, value, type, error)
        result_list = results if isinstance(results, list) else [results]
        for item in result_list:

            tag_name = item.tag

            if item.error:
                print(f"Tag {tag_name} error: {item.error}")
                continue

            value = item.value
            fval = _tag_value_to_float(value)

            if fval is None:
                continue

            mapping = crud.get_device_by_tag(db, tag_name)

            if not mapping:
                continue

            reading = schemas.SensorReadingCreate(
                device_id=mapping.device_id,
                reading=fval,
                status="OK",
            )
            crud.create_sensor_reading(db, reading)

        print("PLC values saved for tags:", tag_names)

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
