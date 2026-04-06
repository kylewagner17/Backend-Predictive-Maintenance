"""
Proof-of-concept synthetic sensor feed when TESTING=1.
Writes realistic-ish time-series per device and logs each sample to the console.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from app import crud, schemas
from app.config import settings
from app.database import SessionLocal
from app.analysis.predict import run_predictions_all_devices


# Simulation parameters keyed by device name (must match seed_devices entries).
_PROFILES: dict[str, dict[str, Any]] = {
    "Conveyor_Bearing_Vibration": {
        "base": 2.2,
        "amp": 0.35,
        "noise": 0.08,
        "escalate_after": 25,
        "escalate_rate": 0.06,
    },
    "Pump_Discharge_Temperature": {
        "base": 52.0,
        "amp": 0.4,
        "noise": 0.15,
        "escalate_after": 20,
        "escalate_rate": 0.35,
    },
    "Spindle_Drive_Current": {
        "base": 11.5,
        "amp": 0.6,
        "noise": 0.12,
        "escalate_after": 9999,
        "escalate_rate": 0.0,
    },
    "Line_Air_Pressure": {
        "base": 87.0,
        "amp": 4.0,
        "noise": 0.5,
        "escalate_after": 40,
        "escalate_rate": -0.12,
    },
    "Coolant_Tank_Level": {
        "base": 62.0,
        "amp": 1.5,
        "noise": 0.2,
        "escalate_after": 9999,
        "escalate_rate": 0.0,
    },
    "Hydraulic_System_Pressure": {
        "base": 2100.0,
        "amp": 80.0,
        "noise": 25.0,
        "escalate_after": 35,
        "escalate_rate": 2.5,
    },
}

_tick_by_device: dict[int, int] = {}


def _value_for_device(name: str, tick: int) -> float:
    p = _PROFILES.get(
        name,
        {"base": 50.0, "amp": 2.0, "noise": 0.5, "escalate_after": 9999, "escalate_rate": 0.0},
    )
    t = tick * 0.25
    wave = math.sin(t) * p["amp"]
    noise = random.gauss(0, p["noise"])
    extra = 0.0
    if tick >= p["escalate_after"]:
        extra = (tick - p["escalate_after"]) * p["escalate_rate"]
    return max(0.0, p["base"] + wave + noise + extra)


def _poll_synthetic_once() -> None:
    db = SessionLocal()
    try:
        devices = crud.get_devices(db)
        if not devices:
            print("[SYNTHETIC] No devices in DB; run with TESTING=1 so seed runs at startup.")
            return

        for d in sorted(devices, key=lambda x: x.id):
            tick = _tick_by_device.get(d.id, 0) + 1
            _tick_by_device[d.id] = tick
            value = _value_for_device(d.name, tick)
            crud.create_sensor_reading(
                db,
                schemas.SensorReadingCreate(device_id=d.id, reading=round(value, 3), status="OK"),
            )
            print(f"[SYNTHETIC] device_id={d.id} name={d.name!r} reading={value:.3f} -> stored")
    finally:
        db.close()


def synthetic_loop() -> None:
    """Background loop: insert synthetic readings and periodically run analysis (POC)."""
    analysis_every = max(1, int(settings.poc_analysis_interval_seconds / max(settings.synthetic_poll_interval_seconds, 0.5)))
    cycle = 0
    print(
        "[SYNTHETIC] POC ingest started (interval="
        f"{settings.synthetic_poll_interval_seconds}s, analysis every {analysis_every} cycle(s))"
    )
    while True:
        try:
            _poll_synthetic_once()
            cycle += 1
            if cycle % analysis_every == 0:
                db = SessionLocal()
                try:
                    print("[SYNTHETIC] Running predictive maintenance analysis…")
                    run_predictions_all_devices(db)
                finally:
                    db.close()
        except Exception as e:
            print("[SYNTHETIC] loop error:", e)
        time.sleep(settings.synthetic_poll_interval_seconds)
