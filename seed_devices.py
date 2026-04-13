"""
Idempotent seed: devices, plc_tag_map (inputs), plc_status_tag_map (DINT outputs).

Run: python seed_devices.py
Controller must define DINT tags for each PM_*_Status name (values 0/1/2).
"""
from app.database import SessionLocal
from app import crud, models, schemas

DEVICE_ROWS = [
    ("Conveyor_Bearing_Vibration", "Conv_Bearing_Vib_mm_s", "PM_Conveyor_Bearing_Status"),
    ("Pump_Discharge_Temperature", "Pump_Discharge_Temp_C", "PM_Pump_Discharge_Status"),
    ("Spindle_Drive_Current", "Spindle_Drive_I_A", "PM_Spindle_Status"),
    ("Line_Air_Pressure", "Line_AirPress_PSI", "PM_Line_Air_Status"),
    ("Coolant_Tank_Level", "Coolant_Tank_Level_Pct", "PM_Coolant_Level_Status"),
    ("Hydraulic_System_Pressure", "Hydraulic_Press_PSI", "PM_Hydraulic_Status"),
]


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
        ensure_demo_devices_seeded(db)
        print("Seed complete (devices + plc_tag_map + plc_status_tag_map).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
