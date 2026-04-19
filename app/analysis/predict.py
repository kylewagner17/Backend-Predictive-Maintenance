"""Rule-based maintenance scoring from recent sensor readings."""

from __future__ import annotations

import os
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from app import crud, schemas
from app.ingest.plc_status import push_maintenance_status_to_plc, push_op300_outputs_to_plc
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

_OP300_SUCCESS_NAME = "Successful_OP300s"
_OP300_UNSUCCESS_NAME = "Unsuccessful_OP300s"
_OP300_OUTPUT_DEVICE_NAME = "OP300_Outputs"


def _should_run_op300_counter_analysis(devices) -> bool:
    names = {d.name for d in devices}
    return (
        _OP300_SUCCESS_NAME in names
        and _OP300_UNSUCCESS_NAME in names
        and _OP300_OUTPUT_DEVICE_NAME in names
    )


def _compute_op300_outputs(
    *,
    success_acc: float,
    unsuccess_acc: float,
    prev_s: float | None,
    prev_u: float | None,
    consecutive: int,
) -> tuple[int, int, int, int, float, float, str]:
    """Return valves_good, inspection_needed, maintenance, new_consecutive, prev_s, prev_u, details."""
    if prev_s is None:
        return (
            1,
            0,
            0,
            0,
            success_acc,
            unsuccess_acc,
            "OP300 bootstrap: Valves_Good=1",
        )

    d_s = success_acc - prev_s
    d_u = unsuccess_acc - prev_u

    if d_s < 0 or d_u < 0:
        return (
            0,
            0,
            0,
            0,
            success_acc,
            unsuccess_acc,
            "OP300 counter decreased (reset/wrap); latched cleared",
        )

    if d_s > 0:
        had_failures = consecutive > 0
        vg = 1 if had_failures else 0
        return (
            vg,
            0,
            0,
            0,
            success_acc,
            unsuccess_acc,
            f"OP300 successful pulse ΔS={d_s}; Valves_Good={vg}",
        )

    if d_u > 0:
        incr = max(1, int(round(abs(d_u))))
        new_c = consecutive + incr
        if new_c >= 2:
            return (
                0,
                0,
                1,
                new_c,
                success_acc,
                unsuccess_acc,
                f"OP300 unsuccessful ΔU={d_u}; consecutive={new_c} → Maintenance",
            )
        return (
            0,
            1,
            0,
            new_c,
            success_acc,
            unsuccess_acc,
            f"OP300 unsuccessful ΔU={d_u}; consecutive=1 → Inspection_Needed",
        )

    if consecutive >= 2:
        return (
            0,
            0,
            1,
            consecutive,
            success_acc,
            unsuccess_acc,
            f"OP300 latched Maintenance (consecutive={consecutive})",
        )
    if consecutive == 1:
        return (
            0,
            1,
            0,
            consecutive,
            success_acc,
            unsuccess_acc,
            f"OP300 latched Inspection_Needed (consecutive={consecutive})",
        )

    return (
        0,
        0,
        0,
        consecutive,
        success_acc,
        unsuccess_acc,
        "OP300 steady (no ACC delta)",
    )


def _op300_recommendation_tag(
    *,
    valves_good: int,
    inspection_needed: int,
    maintenance: int,
) -> str:
    if maintenance:
        return "MAINTENANCE_REQUIRED"
    if inspection_needed:
        return "INSPECT_SOON"
    return "OK"


def run_op300_counter_predictions(db: Session) -> dict[int, str]:
    dev_s = crud.get_device_by_name(db, _OP300_SUCCESS_NAME)
    dev_u = crud.get_device_by_name(db, _OP300_UNSUCCESS_NAME)
    dev_out = crud.get_device_by_name(db, _OP300_OUTPUT_DEVICE_NAME)
    if not dev_s or not dev_u or not dev_out:
        print("[ANALYSIS] OP300 layout incomplete; skipping.")
        return {}

    rs = crud.get_readings_for_device(db, dev_s.id, limit=1)
    ru = crud.get_readings_for_device(db, dev_u.id, limit=1)
    if not rs or not ru:
        print("[ANALYSIS] OP300 skipped (missing readings on one or both counters)")
        return {}

    s_acc = float(rs[0].reading)
    u_acc = float(ru[0].reading)

    state = crud.get_or_create_op300_state(db)
    (
        vg,
        ins,
        maint,
        new_c,
        _,
        _,
        details,
    ) = _compute_op300_outputs(
        success_acc=s_acc,
        unsuccess_acc=u_acc,
        prev_s=state.prev_success_acc,
        prev_u=state.prev_unsuccess_acc,
        consecutive=state.consecutive_unsuccessful,
    )

    crud.save_op300_state(
        db,
        consecutive_unsuccessful=new_c,
        prev_success_acc=s_acc,
        prev_unsuccess_acc=u_acc,
    )

    rec = _op300_recommendation_tag(
        valves_good=vg, inspection_needed=ins, maintenance=maint
    )

    latest_pred, _ = crud.get_latest_two_predictions_for_device(db, dev_out.id)
    old_recommendation = latest_pred.recommendation if latest_pred else None

    snap = [
        {"tag": "Successful_OP300s.ACC", "reading": s_acc},
        {"tag": "Unsuccessful_OP300s.ACC", "reading": u_acc},
    ]

    conf = 1.0 if maint or ins else (0.85 if vg else 0.5)

    crud.create_maintenance_prediction(
        db,
        schemas.MaintenancePredictionCreate(
            device_id=dev_out.id,
            recommendation=rec,
            confidence=conf,
            details=details,
            readings_snapshot=snap,
        ),
    )

    crud.update_device_status_field(db, dev_out.id, rec)

    print(f"[ANALYSIS] OP300 counters S={s_acc} U={u_acc} → out VG={vg} INS={ins} MAINT={maint} | {details}")

    notify_subscribers_on_recommendation_change(
        db,
        dev_out.id,
        dev_out.name,
        old_recommendation,
        rec,
    )

    push_op300_outputs_to_plc(
        db,
        output_device_id=dev_out.id,
        valves_good=vg,
        inspection_needed=ins,
        maintenance=maint,
    )

    return {dev_out.id: rec}


def run_predictions_all_devices(db: Session) -> dict[int, str]:
    devices = crud.get_devices(db)
    if _should_run_op300_counter_analysis(devices):
        print("[ANALYSIS] OP300 dual-counter layout detected.")
        return run_op300_counter_predictions(db)

    outcomes: dict[int, str] = {}
    print(f"[ANALYSIS] Running predictions for {len(devices)} device(s)...")
    for d in devices:
        rec = run_predictions_for_device(db, d.id)
        if rec is not None:
            outcomes[d.id] = rec
    print("[ANALYSIS] Cycle complete.")
    push_maintenance_status_to_plc(db, outcomes)
    return outcomes


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
