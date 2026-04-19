# Predictive maintenance backend — overview

This service ingests sensor-style readings, scores them with rule-based “predictive maintenance” logic, and exposes everything through a FastAPI API. Postgres is the intended production database; local POC mode can use SQLite.

## How data flows end to end

1. **Inputs** — In production, `app/ingest/plc.py` polls a CompactLogix over EtherNet/IP (pycomm3), reads float tags, and maps each tag to a device via `plc_tag_map`. With `TESTING=1`, a synthetic thread can generate demo readings instead of hitting a PLC.

2. **Storage** — Readings are not stored in one giant `sensor_readings` table anymore. Each device gets its own tables: `device_{id}_readings` for live samples (timestamped), `device_{id}_predictions` for each analysis run (also timestamped, including a JSON snapshot of the readings window used), and `device_{id}_readings_archive` for rows moved by retention.

3. **Status row** — The `devices` table holds one row per asset: name, current recommendation string (`OK`, `INSPECT_SOON`, `MAINTENANCE_REQUIRED`, etc.), and `status_updated_at` when that status last changed. That’s the quick “what’s this machine doing right now?” view.

4. **Analysis** — `app/analysis/predict.py` pulls the latest window of readings, applies device-specific thresholds (and some trend/smoothing rules), writes a prediction row, updates `devices.status`, can notify subscribers, and can mirror status to PLC DINT tags via `plc_status_tag_map`.

5. **Triggers** — You can run analysis on demand with `POST /analysis/run`, or let APScheduler fire it on an interval in production. The synthetic POC loop also kicks analysis on its own timer when you’re in testing mode.

## What you’ll find in the repo

- **API** — Health, devices (list + predictions per device), sensor ingest (`POST /sensors/reading`, `GET /sensors/readings/{device_id}`), `POST /analysis/run`, and notification subscription endpoints.
- **ORM models** — `Device`, `PLCTagMap`, `PLCStatusTagMap`, `PushSubscription`, `EmailSubscription`. Time-series live in dynamically named tables wired up in `app/device_storage.py`.
- **Jobs** — `app/jobs/scheduler.py` runs periodic analysis (`maintenance_analysis_interval_minutes`, default 15) and a daily retention pass that archives old readings per device. Both respect `SCHEDULER_ENABLED` and stay off when `TESTING` is on.
- **Config** — `app/config.py` + pydantic-settings: database URL, PLC host/poll interval, retry knobs, notification/SMTP flags, retention timing, synthetic POC timings, log level, etc.

## If you’re extending this

- **Swap in real ML** — The current engine is explicit rules and trends in `predict.py`. Dropping in sklearn, stats, or a small neural net is mostly “build features from the same reading window, return the same recommendation strings” so the PLC and UI layers keep working.
- **Migrations** — Schema today still leans on `create_all` plus `ensure_device_tables` / `sync_tables_for_all_devices` for per-device tables. For a long-lived Postgres instance, Alembic (or another migration tool) is worth adding so you can alter `devices` and manage rollouts without surprises.
- **Production hygiene** — Point `DATABASE_URL` and `PLC_HOST` at real infrastructure, keep `DB_ECHO` off unless you’re debugging SQL, and tune `MAINTENANCE_ANALYSIS_INTERVAL_MINUTES` and retention settings to match how chatty your plant is.

## Handy env vars

```env
DATABASE_URL=postgresql://user:pass@host:5432/maintenance
PLC_HOST=192.168.1.10
PLC_POLL_INTERVAL_SECONDS=10
SCHEDULER_ENABLED=true
MAINTENANCE_ANALYSIS_INTERVAL_MINUTES=15
DB_ECHO=false
```

See `app/config.py` for the full list (retention schedule, SMTP, synthetic intervals, etc.).

## Seed data

`seed_devices.py` is safe to run more than once: it upserts the demo devices and tag maps. You still need matching DINT tags on the controller if you want status writeback to work.

For a deeper dive on running tests locally, see **TESTING.md**.
