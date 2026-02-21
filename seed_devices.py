"""
Seed devices and map controller tag names to devices.
Create controller tags on the CompactLogix (e.g. DINT or REAL) and use those names below.
"""
from app.database import SessionLocal
from app import crud, schemas

db = SessionLocal()

DEVICES = [
    "Laser_1",
    "Proximity_1",
]

# Controller tag names exposed on the 1769-L16ER (must exist in the PLC).
# Change these to match your actual tag names in the controller.
TAG_NAMES = [
    "Laser_1_Value",   # tag for first device
    "Proximity_1_Value",  # tag for second device
]

created_devices = []

for name in DEVICES:
    device = crud.create_device(db, schemas.DeviceCreate(name=name))
    created_devices.append(device)

for i, tag_name in enumerate(TAG_NAMES):
    if i >= len(created_devices):
        break
    crud.create_tag_map(
        db,
        schemas.TagMapCreate(
            tag_name=tag_name,
            device_id=created_devices[i].id,
        ),
    )

db.close()
