"""Analysis tests. Pytest sets PYTEST_CURRENT_TEST so the analyzed sample window is logged to stdout."""
import time

from app import crud, schemas
from app.analysis.predict import run_predictions_for_device, run_predictions_all_devices


def test_run_predictions_for_device_no_readings_does_nothing(db, capsys):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Empty"))
    run_predictions_for_device(db, dev.id)
    out = capsys.readouterr().out
    assert "dataset" not in out
    assert "skipped (no readings)" in out
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 0


def test_run_predictions_for_device_sets_ok_below_threshold(db, capsys):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Low"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=100.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    out = capsys.readouterr().out
    assert "dataset" in out and "n=1 samples" in out
    assert "reading=100.0" in out
    assert "name='Low'" in out
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "OK"
    snap = preds[0].readings_snapshot
    assert snap is not None and len(snap) == 1
    assert snap[0]["reading"] == 100.0 and snap[0]["row_status"] == "OK"


def test_run_predictions_for_device_sets_inspect_soon_mid_range(db, capsys):
    dev = crud.create_device(db, schemas.DeviceCreate(name="Mid"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=600.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    out = capsys.readouterr().out
    assert "dataset" in out and "reading=600.0" in out
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "INSPECT_SOON"


def test_run_predictions_for_device_sets_maintenance_required_high(db, capsys):
    dev = crud.create_device(db, schemas.DeviceCreate(name="High"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=1500.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    out = capsys.readouterr().out
    assert "dataset" in out and "reading=1500.0" in out
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "MAINTENANCE_REQUIRED"


def test_run_predictions_for_device_multi_sample_dataset_order_newest_first(db, capsys):
    """Multiple readings: dataset lists newest first (matches analysis window)."""
    dev = crud.create_device(db, schemas.DeviceCreate(name="Multi"))
    for val in (10.0, 20.0, 30.0):
        crud.create_sensor_reading(
            db,
            schemas.SensorReadingCreate(device_id=dev.id, reading=val, status="OK"),
        )
        time.sleep(0.002)
    run_predictions_for_device(db, dev.id)
    out = capsys.readouterr().out
    assert "n=3 samples" in out
    # Newest-first order: 30 then 20 then 10
    pos_30 = out.index("reading=30.0")
    pos_20 = out.index("reading=20.0")
    pos_10 = out.index("reading=10.0")
    assert pos_30 < pos_20 < pos_10
    preds = crud.get_predictions_for_device(db, dev.id)
    assert len(preds) == 1
    assert preds[0].recommendation == "OK"


def test_run_predictions_all_devices(db, capsys):
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
    out = capsys.readouterr().out
    assert "Running predictions for 2 device(s)" in out
    assert out.count("dataset") == 2
    assert "name='D1'" in out and "reading=200.0" in out
    assert "name='D2'" in out and "reading=700.0" in out
    p1 = crud.get_predictions_for_device(db, d1.id)
    p2 = crud.get_predictions_for_device(db, d2.id)
    assert len(p1) == 1 and p1[0].recommendation == "OK"
    assert len(p2) == 1 and p2[0].recommendation == "INSPECT_SOON"
