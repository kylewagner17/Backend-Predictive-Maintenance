"""Rule-based maintenance scoring from recent sensor readings."""

from __future__ import annotations

import os
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from app import crud, schemas
from app.ingest.plc_status import push_maintenance_status_to_plc
from app.notifications.push import notify_subscribers_on_recommendation_change

# Limits align with seed_devices / synthetic device names.
DEVICE_SPECS: dict[str, dict[str, float | str]] = {
    "Conveyor_Bearing_Vibration": {"warn": 5.0, "crit": 8.0, "unit": "mm/s"},
    "Pump_Discharge_Temperature": {"warn": 70.0, "crit": 85.0, "unit": "degC"},
    "Spindle_Drive_Current": {"warn": 18.0, "crit": 22.0, "unit": "A"},
    "Line_Air_Pressure": {"warn": 72.0, "crit": 65.0, "unit": "PSI"},
    "Coolant_Tank_Level": {"warn": 35.0, "crit": 20.0, "unit": "%"},
    "Hydraulic_System_Pressure": {"warn": 2800.0, "crit": 3200.0, "unit": "PSI"},
}

_DEFAULT_WARN = 500.0
_DEFAULT_CRIT = 1000.0
_MIN_SAMPLES_TREND = 5
_WINDOW = 40
_SMOOTH_SPAN = 3  # newest-only moving average for limit checks (spec devices)


def _log_analysis_dataset_enabled() -> bool:
    if os.environ.get("ANALYSIS_LOG_DATASET", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _readings_to_snapshot(readings) -> list[dict]:
    """Same datapoints as analysis logging / per-device predictions JSON column."""
    out: list[dict] = []
    for r in readings:
        ts = r.timestamp
        ts_s = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        out.append(
            {
                "id": r.id,
                "recorded_at": ts_s,
                "reading": r.reading,
                "row_status": r.status,
            }
        )
    return out


def _print_analysis_dataset(device_id: int, device_name: str, readings) -> None:
    lines = [
        f"[ANALYSIS] dataset device_id={device_id} name={device_name!r} "
        f"n={len(readings)} samples (newest first, limit={_WINDOW}):"
    ]
    for i, r in enumerate(readings):
        ts = r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else r.timestamp
        lines.append(f"  [{i}] ts={ts}  reading={r.reading!r}  status={r.status!r}")
    print("\n".join(lines))


def _slope_simple(values_oldest_to_newest: list[float]) -> float:
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


def _smoothed_head(values_newest_first: list[float], span: int = _SMOOTH_SPAN) -> float:
    if not values_newest_first:
        return 0.0
    take = values_newest_first[: min(span, len(values_newest_first))]
    return mean(take)


def _sustained_critical(
    *,
    low_is_bad: bool,
    crit: float,
    v0: float,
    v1: float,
) -> bool:
    if low_is_bad:
        return v0 <= crit and v1 <= crit
    return v0 >= crit and v1 >= crit


def _evaluate_device(name: str, values_newest_first: list[float]) -> tuple[str, float | None, str]:
    """values_newest_first: time-desc (index 0 = newest). Returns recommendation, confidence, details."""
    latest = values_newest_first[0]
    spec = DEVICE_SPECS.get(name)
    if spec:
        warn = float(spec["warn"])
        crit = float(spec["crit"])
        unit = str(spec["unit"])
        low_is_bad = name in ("Line_Air_Pressure", "Coolant_Tank_Level")
        effective = _smoothed_head(values_newest_first, _SMOOTH_SPAN)

        if low_is_bad:
            if effective <= crit:
                rec, conf, det = (
                    "MAINTENANCE_REQUIRED",
                    0.85,
                    f"Smoothed {effective:.2f}{unit} at/below critical (<={crit}); latest={latest:.2f}.",
                )
            elif effective <= warn:
                rec, conf, det = (
                    "INSPECT_SOON",
                    0.65,
                    f"Smoothed {effective:.2f}{unit} below warning (<={warn}); latest={latest:.2f}.",
                )
            else:
                rec, conf, det = None, None, ""
        else:
            if effective >= crit:
                rec, conf, det = (
                    "MAINTENANCE_REQUIRED",
                    0.85,
                    f"Smoothed {effective:.2f}{unit} at/above critical (>={crit}); latest={latest:.2f}.",
                )
            elif effective >= warn:
                rec, conf, det = (
                    "INSPECT_SOON",
                    0.7,
                    f"Smoothed {effective:.2f}{unit} above warning (>={warn}); latest={latest:.2f}.",
                )
            else:
                rec, conf, det = None, None, ""

        if rec == "MAINTENANCE_REQUIRED":
            # Two raw samples must both be in critical; smoothed alone is not enough.
            if len(values_newest_first) < 2:
                rec, conf, det = (
                    "INSPECT_SOON",
                    0.6,
                    det + " Downgraded: need 2+ samples to confirm critical.",
                )
            else:
                v0, v1 = values_newest_first[0], values_newest_first[1]
                if not _sustained_critical(low_is_bad=low_is_bad, crit=crit, v0=v0, v1=v1):
                    rec, conf, det = (
                        "INSPECT_SOON",
                        0.62,
                        det + " Downgraded: critical not sustained on last two raw samples.",
                    )

        if rec is None:
            oldest_first = list(reversed(values_newest_first[:_WINDOW]))
            if len(oldest_first) >= _MIN_SAMPLES_TREND:
                slope = _slope_simple(oldest_first)
                m = mean(oldest_first)
                sd = pstdev(oldest_first) if len(oldest_first) > 1 else 0.0
                if not low_is_bad and slope > 0 and latest > m + 0.5 * sd and latest > warn * 0.75:
                    return (
                        "INSPECT_SOON",
                        0.55,
                        f"Upward trend (slope={slope:.4f}/sample); mean={m:.2f}{unit}; latest={latest:.2f}.",
                    )
                if low_is_bad and slope < 0 and latest < m:
                    return (
                        "INSPECT_SOON",
                        0.55,
                        f"Falling trend (slope={slope:.4f}/sample); mean={m:.2f}{unit}; latest={latest:.2f}.",
                    )

            return "OK", 0.5, f"Within band; smoothed={effective:.2f}{unit} latest={latest:.2f}."

        return rec, conf, det

    # Unmapped device names: fixed thresholds for tests.
    if latest >= _DEFAULT_CRIT:
        return "MAINTENANCE_REQUIRED", 0.8, f"Latest reading {latest:.2f} >= {_DEFAULT_CRIT} (default scale)."
    if latest >= _DEFAULT_WARN:
        return "INSPECT_SOON", 0.65, f"Latest reading {latest:.2f} >= {_DEFAULT_WARN} (default scale)."
    return "OK", 0.5, f"Latest reading {latest:.2f} within default OK band."


def run_predictions_for_device(db: Session, device_id: int) -> str | None:
    readings = crud.get_readings_for_device(db, device_id, limit=_WINDOW)
    if not readings:
        device = crud.get_device_by_id(db, device_id)
        label = device.name if device else str(device_id)
        print(f"[ANALYSIS] device_id={device_id} name={label!r} -> skipped (no readings)")
        return None

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
            readings_snapshot=_readings_to_snapshot(readings),
        ),
    )

    crud.update_device_status_field(db, device_id, recommendation)

    conf_s = f"{confidence:.2f}" if confidence is not None else "n/a"
    print(
        f"[ANALYSIS] device_id={device_id} name={device_name!r} -> {recommendation} "
        f"(confidence={conf_s}) | {details}"
    )

    notify_subscribers_on_recommendation_change(
        db, device_id, device_name, old_recommendation, recommendation
    )
    return recommendation


def run_predictions_all_devices(db: Session) -> dict[int, str]:
    devices = crud.get_devices(db)
    print(f"[ANALYSIS] Running predictions for {len(devices)} device(s)...")
    outcomes: dict[int, str] = {}
    for d in devices:
        rec = run_predictions_for_device(db, d.id)
        if rec is not None:
            outcomes[d.id] = rec
    print("[ANALYSIS] Cycle complete.")
    push_maintenance_status_to_plc(db, outcomes)
    return outcomes
