"""
Analysis (predictive maintenance) logic tests.
Run with: pytest test_analysis.py -v
"""
from app import crud, schemas
from app.analysis.predict import run_predictions_for_device, run_predictions_all_devices


def test_run_predictions_for_device_no_readings_does_nothing(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Empty"))
    run_predictions_for_device(db, dev.id)
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 0


def test_run_predictions_for_device_sets_ok_below_threshold(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Low"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=100.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "OK"


def test_run_predictions_for_device_sets_inspect_soon_mid_range(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Mid"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=600.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "INSPECT_SOON"


def test_run_predictions_for_device_sets_maintenance_required_high(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="High"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=1500.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "MAINTENANCE_REQUIRED"


def test_run_predictions_all_devices(db):
    d1 = crud.create_device(db, schemas.DeviceCreate(name="D1"))
    d2 = crud.create_device(db, schemas.DeviceCreate(name="D2"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=d1.id, reading=200.0, status="OK"),
    )
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=d2.id, reading=700.0, status="OK"),
    )
    run_predictions_all_devices(db)
    p1 = crud.get_predictions_for_device(db, d1.id)
    p2 = crud.get_predictions_for_device(db, d2.id)
    assert len(p1) == 1 and p1[0].recommendation == "OK"
    assert len(p2) == 1 and p2[0].recommendation == "INSPECT_SOON"
