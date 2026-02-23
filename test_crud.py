"""
CRUD layer tests. Use db fixture for an isolated in-memory DB.
Run with: pytest test_crud.py -v
"""
from app import crud, schemas


def test_create_device(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Laser_1"))
    assert dev.id is not None
    assert dev.name == "Laser_1"
    assert dev.status == "OK"


def test_get_devices(db):
    crud.create_device(db, schemas.DeviceCreate(name="A"))
    crud.create_device(db, schemas.DeviceCreate(name="B"))
    all_devs = crud.get_devices(db)
    assert len(all_devs) == 2
    names = {d.name for d in all_devs}
    assert names == {"A", "B"}


def test_create_sensor_reading(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="S"))
    reading = crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=100.0, status="OK"),
    )
    assert reading.id is not None
    assert reading.device_id == dev.id
    assert reading.reading == 100.0
    assert reading.timestamp is not None


def test_get_readings_for_device(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="D"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=1.0, status="OK"),
    )
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=2.0, status="OK"),
    )
    readings = crud.get_readings_for_device(db, dev.id, limit=10)
    assert len(readings) == 2
    assert {r.reading for r in readings} == {1.0, 2.0}


def test_create_tag_map(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="T"))
    m = crud.create_tag_map(db, schemas.TagMapCreate(tag_name="MyTag", device_id=dev.id))
    assert m.id is not None
    assert m.tag_name == "MyTag"
    assert m.device_id == dev.id


def test_get_device_by_tag(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="X"))
    crud.create_tag_map(db, schemas.TagMapCreate(tag_name="TagX", device_id=dev.id))
    mapping = crud.get_device_by_tag(db, "TagX")
    assert mapping is not None
    assert mapping.device_id == dev.id


def test_get_all_tag_mappings(db):
    dev1 = crud.create_device(db, schemas.DeviceCreate(name="D1"))
    dev2 = crud.create_device(db, schemas.DeviceCreate(name="D2"))
    crud.create_tag_map(db, schemas.TagMapCreate(tag_name="T1", device_id=dev1.id))
    crud.create_tag_map(db, schemas.TagMapCreate(tag_name="T2", device_id=dev2.id))
    mappings = crud.get_all_tag_mappings(db)
    assert len(mappings) == 2
    tag_to_dev = {m.tag_name: m.device_id for m in mappings}
    assert tag_to_dev == {"T1": dev1.id, "T2": dev2.id}


def test_create_maintenance_prediction(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="P"))
    pred = crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(
            device_id=dev.id,
            recommendation="OK",
            confidence=None,
            details="test",
        ),
    )
    assert pred.id is not None
    assert pred.recommendation == "OK"
    assert pred.device_id == dev.id


def test_get_latest_two_predictions_for_device(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Q"))
    latest, prev = crud.get_latest_two_predictions_for_device(db, dev.id)
    assert latest is None
    assert prev is None

    crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(device_id=dev.id, recommendation="OK"),
    )
    latest, prev = crud.get_latest_two_predictions_for_device(db, dev.id)
    assert latest is not None
    assert latest.recommendation == "OK"
    assert prev is None

    crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(device_id=dev.id, recommendation="INSPECT_SOON"),
    )
    latest, prev = crud.get_latest_two_predictions_for_device(db, dev.id)
    assert latest.recommendation == "INSPECT_SOON"
    assert prev.recommendation == "OK"
