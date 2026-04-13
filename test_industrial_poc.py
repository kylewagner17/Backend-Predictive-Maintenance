"""Tests for PLC status write path, retention, SMTP gating, and analysis rules (mocked PLC)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app import crud, schemas
from app.device_storage import count_archived_readings, count_readings
from app.analysis.predict import _evaluate_device, run_predictions_for_device
from app.ingest.plc_status import RECOMMENDATION_TO_DINT, push_maintenance_status_to_plc
from app.notifications.push import notify_subscribers_on_recommendation_change


def test_poc_recommendation_dint_codes_for_hmi():
    assert RECOMMENDATION_TO_DINT["OK"] == 0
    assert RECOMMENDATION_TO_DINT["INSPECT_SOON"] == 1
    assert RECOMMENDATION_TO_DINT["MAINTENANCE_REQUIRED"] == 2


def test_poc_smoothing_prevents_single_sample_spike_trip():
    name = "Conveyor_Bearing_Vibration"
    vals = [8.6, 2.0, 2.0]  # newest first; head mean < warn
    rec, conf, det = _evaluate_device(name, vals)
    assert rec == "OK"
    assert "smoothed" in det.lower()


def test_poc_sustained_critical_maintenance_required():
    name = "Conveyor_Bearing_Vibration"
    vals = [9.0, 9.0, 9.0]
    rec, _, det = _evaluate_device(name, vals)
    assert rec == "MAINTENANCE_REQUIRED"
    assert "sustained" not in det.lower() or "smoothed" in det.lower()


def test_poc_downgrade_maintenance_when_critical_not_sustained_on_two_raw_samples():
    name = "Conveyor_Bearing_Vibration"
    vals = [9.0, 7.0, 15.0]  # smoothed mean > crit; second raw 7 < crit 8
    rec, _, det = _evaluate_device(name, vals)
    assert rec == "INSPECT_SOON"
    assert "sustained" in det.lower() or "Downgraded" in det


def test_poc_pump_discharge_maintenance_required_when_hot_and_sustained():
    name = "Pump_Discharge_Temperature"
    vals = [92.0, 91.0, 90.0]  # newest first; crit 85
    rec, _, det = _evaluate_device(name, vals)
    assert rec == "MAINTENANCE_REQUIRED"
    assert "critical" in det.lower()


def test_poc_line_air_maintenance_required_when_pressure_collapsed():
    name = "Line_Air_Pressure"
    vals = [62.0, 63.0, 64.0]  # newest first; crit 65 (low is bad)
    rec, _, det = _evaluate_device(name, vals)
    assert rec == "MAINTENANCE_REQUIRED"
    assert "critical" in det.lower()


def test_poc_retention_moves_rows_to_archive(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="RetentionDev"))
    old_ts = datetime.now(timezone.utc) - timedelta(days=200)
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(
            device_id=dev.id,
            reading=3.14,
            status="OK",
            recorded_at=old_ts,
        ),
    )

    n = crud.archive_sensor_readings_older_than(db, older_than_days=90, batch_size=500)
    assert n == 1

    assert count_readings(db, dev.id) == 0
    assert count_archived_readings(db, dev.id) == 1


def test_poc_plc_status_write_calls_controller_write(db, monkeypatch):
    monkeypatch.setattr("app.ingest.plc_status.settings.testing", False)
    monkeypatch.setattr("app.ingest.plc_status.settings.plc_status_write_enabled", True)

    dev = crud.create_device(db, schemas.DeviceCreate(name="PLCWriteDev"))
    crud.create_status_tag_map(
        db,
        schemas.StatusTagMapCreate(tag_name="PM_POC_Status", device_id=dev.id),
    )

    mock_plc = MagicMock()
    mock_plc.write = MagicMock()

    @contextmanager
    def fake_session():
        yield mock_plc

    with patch("app.ingest.plc_status.logix_driver_session", fake_session):
        with patch("app.ingest.plc_status.retry_with_backoff", lambda fn, **kw: fn()):
            push_maintenance_status_to_plc(
                db,
                {dev.id: "INSPECT_SOON"},
            )

    mock_plc.write.assert_called_once()
    args, _ = mock_plc.write.call_args
    assert ("PM_POC_Status", 1) in args or args == (("PM_POC_Status", 1),)


def test_poc_plc_push_skipped_in_testing_mode(db, monkeypatch):
    monkeypatch.setattr("app.ingest.plc_status.settings.testing", True)
    dev = crud.create_device(db, schemas.DeviceCreate(name="NoPLC"))
    crud.create_status_tag_map(
        db,
        schemas.StatusTagMapCreate(tag_name="PM_X", device_id=dev.id),
    )
    with patch("app.ingest.plc_status.logix_driver_session") as m:
        push_maintenance_status_to_plc(db, {dev.id: "OK"})
    m.assert_not_called()


def test_poc_email_only_when_smtp_configured(monkeypatch, db):
    monkeypatch.setattr("app.notifications.push.settings.notifications_enabled", True)
    monkeypatch.setattr("app.notifications.push.settings.smtp_host", "")
    sent: list[tuple] = []

    def capture(to, subj, body):
        sent.append((to, subj, body))
        return True

    monkeypatch.setattr("app.notifications.push.send_email", capture)

    dev = crud.create_device(db, schemas.DeviceCreate(name="MailDev"))
    crud.create_email_subscription(
        db,
        schemas.EmailSubscriptionCreate(email="operator@example.com", device_id=dev.id),
    )

    notify_subscribers_on_recommendation_change(db, dev.id, "MailDev", "OK", "INSPECT_SOON")
    assert sent == []

    monkeypatch.setattr("app.notifications.push.settings.smtp_host", "smtp.example.com")
    notify_subscribers_on_recommendation_change(
        db, dev.id, "MailDev", "INSPECT_SOON", "MAINTENANCE_REQUIRED"
    )
    assert len(sent) == 1
    assert sent[0][0] == "operator@example.com"


def test_poc_device_table_status_matches_recommendation(db):
    dev = crud.create_device(db, schemas.DeviceCreate(name="StatusSync"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(device_id=dev.id, reading=100.0, status="OK"),
    )
    run_predictions_for_device(db, dev.id)
    again = crud.get_device_by_id(db, dev.id)
    assert again is not None
    assert again.status == "OK"


def test_poc_retention_module_batch(monkeypatch, db):
    from app.jobs import retention

    dev = crud.create_device(db, schemas.DeviceCreate(name="JobDev"))
    crud.create_sensor_reading(
        db,
        schemas.SensorReadingCreate(
            device_id=dev.id,
            reading=1.0,
            status="OK",
            recorded_at=datetime.now(timezone.utc) - timedelta(days=500),
        ),
    )

    monkeypatch.setattr("app.jobs.retention.settings.sensor_readings_retention_days", 90)
    monkeypatch.setattr("app.jobs.retention.settings.retention_batch_size", 500)

    n = retention.run_sensor_readings_retention()
    assert n == 1


def test_poc_scheduler_does_not_start_under_testing_mode(monkeypatch):
    from app.config import settings
    from app.jobs.scheduler import start_scheduler

    monkeypatch.setattr(settings, "testing", True)
    assert start_scheduler() is None
