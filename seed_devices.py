"""
Seed devices and PLC tag mappings (idempotent).

Run manually: python seed_devices.py
When the app starts with TESTING=1, ensure_demo_devices_seeded() runs from main.
"""
from app.database import SessionLocal
from app import crud, models, schemas

# Example assets for predictive maintenance demos (names align with synthetic + analysis thresholds).
DEVICE_TAG_PAIRS = [
    ("Conveyor_Bearing_Vibration", "Conv_Bearing_Vib_mm_s"),
    ("Pump_Discharge_Temperature", "Pump_Discharge_Temp_C"),
    ("Spindle_Drive_Current", "Spindle_Drive_I_A"),
    ("Line_Air_Pressure", "Line_AirPress_PSI"),
    ("Coolant_Tank_Level", "Coolant_Tank_Level_Pct"),
    ("Hydraulic_System_Pressure", "Hydraulic_Press_PSI"),
]


def ensure_demo_devices_seeded(db) -> None:
    """Create devices and tag maps if missing; update tag map device_id if tag exists."""
    for device_name, tag_name in DEVICE_TAG_PAIRS:
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


def main() -> None:
    db = SessionLocal()
    try:
        ensure_demo_devices_seeded(db)
        print("Seed complete (devices + plc_tag_map).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
