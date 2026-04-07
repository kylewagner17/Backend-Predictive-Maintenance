"""
Predictive maintenance (POC): rolling statistics, trend, and per-device thresholds.
Logs each result to the console for demonstration.
"""
from __future__ import annotations

import os
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from app import crud, schemas
from app.notifications.push import notify_subscribers_on_recommendation_change

# Thresholds for seeded demo devices (units match synthetic ingest / typical plant sensors).
DEVICE_SPECS: dict[str, dict[str, float | str]] = {
    "Conveyor_Bearing_Vibration": {"warn": 5.0, "crit": 8.0, "unit": "mm/s"},
    "Pump_Discharge_Temperature": {"warn": 70.0, "crit": 85.0, "unit": "degC"},
    "Spindle_Drive_Current": {"warn": 18.0, "crit": 22.0, "unit": "A"},
    "Line_Air_Pressure": {"warn": 72.0, "crit": 65.0, "unit": "PSI"},  # low pressure is bad
    "Coolant_Tank_Level": {"warn": 35.0, "crit": 20.0, "unit": "%"},  # low level is bad
    "Hydraulic_System_Pressure": {"warn": 2800.0, "crit": 3200.0, "unit": "PSI"},
}

# Default thresholds for ad-hoc / test device names (legacy tests use "Low", "Mid", "High").
_DEFAULT_WARN = 500.0
_DEFAULT_CRIT = 1000.0
_MIN_SAMPLES_TREND = 5
_WINDOW = 40


def _log_analysis_dataset_enabled() -> bool:
    """Full sample listing for pytest runs or when ANALYSIS_LOG_DATASET=1."""
    if os.environ.get("ANALYSIS_LOG_DATASET", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _print_analysis_dataset(device_id: int, device_name: str, readings) -> None:
    """Print readings window used by _evaluate_device (newest first, same order as crud query)."""
    lines = [
        f"[ANALYSIS] dataset device_id={device_id} name={device_name!r} "
        f"n={len(readings)} samples (newest first, limit={_WINDOW}):"
    ]
    for i, r in enumerate(readings):
        ts = r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else r.timestamp
        lines.append(f"  [{i}] ts={ts}  reading={r.reading!r}  status={r.status!r}")
    print("\n".join(lines))


def _slope_simple(values_oldest_to_newest: list[float]) -> float:
    """Least-squares slope for evenly spaced samples."""
    n = len(values_oldest_to_newest)
    if n < 2:
        return 0.0
    xs = list(range(n))
    ys = values_oldest_to_newest
    x_m = mean(xs)
    y_m = mean(ys)
    num = sum((x - x_m) * (y - y_m) for x, y in zip(xs, ys))
    den = sum((x - x_m) ** 2 for x in xs) or 1e-9
    return num / den


def _evaluate_device(name: str, values_newest_first: list[float]) -> tuple[str, float | None, str]:
    """
    values_newest_first: readings ordered by time desc (index 0 = latest).
    Returns (recommendation, confidence, details).
    """
    latest = values_newest_first[0]
    spec = DEVICE_SPECS.get(name)
    if spec:
        warn = float(spec["warn"])
        crit = float(spec["crit"])
        unit = str(spec["unit"])
        low_is_bad = name in ("Line_Air_Pressure", "Coolant_Tank_Level")

        if low_is_bad:
            if latest <= crit:
                return "MAINTENANCE_REQUIRED", 0.85, f"Latest {latest:.2f}{unit} at/below critical low (<={crit})."
            if latest <= warn:
                return "INSPECT_SOON", 0.65, f"Latest {latest:.2f}{unit} below warning band (<={warn})."
        else:
            if latest >= crit:
                return "MAINTENANCE_REQUIRED", 0.85, f"Latest {latest:.2f}{unit} at/above critical (>={crit})."
            if latest >= warn:
                return "INSPECT_SOON", 0.7, f"Latest {latest:.2f}{unit} above warning (>={warn})."

        # Trend / variability on top of level checks
        oldest_first = list(reversed(values_newest_first[:_WINDOW]))
        if len(oldest_first) >= _MIN_SAMPLES_TREND:
            slope = _slope_simple(oldest_first)
            m = mean(oldest_first)
            sd = pstdev(oldest_first) if len(oldest_first) > 1 else 0.0
            if not low_is_bad and slope > 0 and latest > m + 0.5 * sd and latest > warn * 0.75:
                return "INSPECT_SOON", 0.55, f"Upward trend (slope={slope:.4f}/sample); mean={m:.2f}{unit}."
            if low_is_bad and slope < 0 and latest < m:
                return "INSPECT_SOON", 0.55, f"Falling trend (slope={slope:.4f}/sample); mean={m:.2f}{unit}."

        return "OK", 0.5, f"Within band; latest={latest:.2f}{unit}."

    # Legacy generic numeric scale (unit tests)
    if latest >= _DEFAULT_CRIT:
        return "MAINTENANCE_REQUIRED", 0.8, f"Latest reading {latest:.2f} >= {_DEFAULT_CRIT} (default scale)."
    if latest >= _DEFAULT_WARN:
        return "INSPECT_SOON", 0.65, f"Latest reading {latest:.2f} >= {_DEFAULT_WARN} (default scale)."
    return "OK", 0.5, f"Latest reading {latest:.2f} within default OK band."


def run_predictions_for_device(db: Session, device_id: int) -> None:
    readings = crud.get_readings_for_device(db, device_id, limit=_WINDOW)
    if not readings:
        device = crud.get_device_by_id(db, device_id)
        label = device.name if device else str(device_id)
        print(f"[ANALYSIS] device_id={device_id} name={label!r} -> skipped (no readings)")
        return

    latest_pred, _ = crud.get_latest_two_predictions_for_device(db, device_id)
    old_recommendation = latest_pred.recommendation if latest_pred else None

    device = crud.get_device_by_id(db, device_id)
    device_name = device.name if device else f"device_{device_id}"
    if _log_analysis_dataset_enabled():
        _print_analysis_dataset(device_id, device_name, readings)
    values_nf = [r.reading for r in readings]
    recommendation, confidence, details = _evaluate_device(device_name, values_nf)

    crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(
            device_id=device_id,
            recommendation=recommendation,
            confidence=confidence,
            details=details,
        ),
    )

    conf_s = f"{confidence:.2f}" if confidence is not None else "n/a"
    print(
        f"[ANALYSIS] device_id={device_id} name={device_name!r} -> {recommendation} "
        f"(confidence={conf_s}) | {details}"
    )

    notify_subscribers_on_recommendation_change(
        db, device_id, device_name, old_recommendation, recommendation
    )


def run_predictions_all_devices(db: Session) -> None:
    devices = crud.get_devices(db)
    print(f"[ANALYSIS] Running predictions for {len(devices)} device(s)...")
    for d in devices:
        run_predictions_for_device(db, d.id)
    print("[ANALYSIS] Cycle complete.")
