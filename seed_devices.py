from app.database import SessionLocal
from app import crud, schemas

db = SessionLocal()

DEVICES = [
    "Laser_1",
    "Proximity_1",

]

created_devices = []

for name in DEVICES:
    device = crud.create_device(db, schemas.DeviceCreate(name=name))
    created_devices.append(device)


#map registers only for the amount specificied in the DEVICES list
crud.create_register_map(
    db,
    schemas.RegisterMapCreate(
        register_address=0,
        device_id=created_devices[0].id
    )
)

crud.create_register_map(
    db,
    schemas.RegisterMapCreate(
        register_address=1,
        device_id=created_devices[1].id
    )
)


db.close()
