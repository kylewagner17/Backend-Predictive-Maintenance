"""
Idempotent seed: devices, plc_tag_map (inputs), plc_status_tag_map (outputs).

Run: python seed_devices.py
Clears plc_tag_map, plc_status_tag_map, and devices (nulls subscription device_id FKs), then inserts rows below.

OP300 layout: two CTU ACC inputs and three BOOL/DINT outputs on device OP300_Outputs.
"""
from sqlalchemy import delete, update

from app.database import SessionLocal
from app import crud, models, schemas

INPUT_DEVICES = [
    ("Successful_OP300s", "Successful_OP300s.ACC"),
    ("Unsuccessful_OP300s", "Unsuccessful_OP300s.ACC"),
]

OUTPUT_DEVICE_NAME = "OP300_Outputs"
OUTPUT_STATUS_TAGS = ("Valves_Good", "Inspection_Needed", "Maintenance")


def clear_seed_tables(db) -> None:
    """Remove all tag maps and devices; null out optional device FKs on subscriptions."""
    db.execute(delete(models.PLCTagMap))
    db.execute(delete(models.PLCStatusTagMap))
    db.execute(delete(models.Op300ProcessState))
    db.execute(update(models.PushSubscription).values(device_id=None))
    db.execute(update(models.EmailSubscription).values(device_id=None))
    db.execute(delete(models.Device))
    db.commit()


def ensure_demo_devices_seeded(db) -> None:
    for device_name, tag_name in INPUT_DEVICES:
        existing = (
            db.query(models.Device).filter(models.Device.name == device_name).first()
        )
        if existing:
            device = existing
        else:
            device = crud.create_device(db, schemas.DeviceCreate(name=device_name))
        crud.create_tag_map(
            db,
            schemas.TagMapCreate(tag_name=tag_name, device_id=device.id),
        )

    out_existing = (
        db.query(models.Device)
        .filter(models.Device.name == OUTPUT_DEVICE_NAME)
        .first()
    )
    if out_existing:
        out_dev = out_existing
    else:
        out_dev = crud.create_device(db, schemas.DeviceCreate(name=OUTPUT_DEVICE_NAME))

    for status_tag in OUTPUT_STATUS_TAGS:
        crud.create_status_tag_map(
            db,
            schemas.StatusTagMapCreate(tag_name=status_tag, device_id=out_dev.id),
        )


def main() -> None:
    db = SessionLocal()
    try:
        clear_seed_tables(db)
        ensure_demo_devices_seeded(db)
        print("Seed complete (cleared + OP300 devices + plc_tag_map + plc_status_tag_map).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
