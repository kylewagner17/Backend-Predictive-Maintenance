"""
Idempotent seed: devices, plc_tag_map (inputs), plc_status_tag_map (DINT outputs).

Run: python seed_devices.py
Clears plc_tag_map, plc_status_tag_map, and devices (nulls subscription device_id FKs), then inserts rows below.
Controller should define DINT tags for each status name (values 0/1/2) if status writeback is enabled.
"""
from sqlalchemy import delete, update

from app.database import SessionLocal
from app import crud, models, schemas

DEVICE_ROWS = [
    ("Robot_OP100", "OP100.ACC", "Robot_Status"),
    ("Valve_OP200", "OP200.ACC", "Valve_Status"),
]


def clear_seed_tables(db) -> None:
    """Remove all tag maps and devices; null out optional device FKs on subscriptions."""
    db.execute(delete(models.PLCTagMap))
    db.execute(delete(models.PLCStatusTagMap))
    db.execute(update(models.PushSubscription).values(device_id=None))
    db.execute(update(models.EmailSubscription).values(device_id=None))
    db.execute(delete(models.Device))
    db.commit()


def ensure_demo_devices_seeded(db) -> None:
    for device_name, tag_name, status_tag in DEVICE_ROWS:
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
        crud.create_status_tag_map(
            db,
            schemas.StatusTagMapCreate(tag_name=status_tag, device_id=device.id),
        )


def main() -> None:
    db = SessionLocal()
    try:
        clear_seed_tables(db)
        ensure_demo_devices_seeded(db)
        print("Seed complete (cleared + devices + plc_tag_map + plc_status_tag_map).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
