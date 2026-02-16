# Predictive Maintenance Backend — Overview

## Intended flow

1. **PLC sensor data** → Modbus TCP read (holding registers) in `app/ingest/plc.py`.
2. **Backend** → Maps registers to devices via `plc_register_map`, writes values to `sensor_readings`.
3. **Database** → PostgreSQL stores devices, sensor_readings, and maintenance_predictions.
4. **Analysis** → Logic in `app/analysis/` reads recent readings, runs your model, writes to `maintenance_predictions`. Trigger via `POST /analysis/run` or a scheduled job.

## What’s in place

- **Ingest**: PLC poll loop with configurable host, port, registers, and poll interval (see `.env` / `app/config.py`).
- **Models**: `Device`, `SensorReading`, `PLCRegisterMap`, `MaintenancePrediction`.
- **API**: Health, devices, sensor readings (POST + GET by device), device predictions, and `POST /analysis/run`.
- **Config**: PLC and DB settings via pydantic-settings (env vars / `.env`).

## Recommendations

1. **Scheduling analysis**  
   Run analysis on a schedule (e.g. every 5–15 minutes) instead of only on demand. Options:
   - **APScheduler** inside the FastAPI process (same as your PLC thread).
   - **Celery** or **RQ** with Redis if you want a separate worker.
   - **Cron** calling `POST /analysis/run` (or a management script that uses `run_predictions_all_devices`).

2. **Implement real prediction logic**  
   Replace the stub in `app/analysis/predict.py` with your approach, e.g.:
   - Thresholds or trend (slope) on recent readings.
   - Rolling mean/std and anomaly detection.
   - Scikit-learn / TensorFlow model on features derived from readings (e.g. last N values, variance, min/max).

3. **Migrations**  
   Use **Alembic** for schema changes so you don’t rely only on `create_all` and can evolve the DB safely (e.g. new columns, indexes).

4. **Seed script**  
   `seed_devices.py` will fail on a second run (duplicate devices/registers). Make it idempotent (e.g. get_or_create by name, create register maps only if missing) or run it once and use migrations for future data changes.

5. **Production**  
   - Set `PLC_*` and `DATABASE_URL` in the environment (or `.env`), not in code.
   - Use `db_echo=False` (default now) so logs aren’t filled with SQL.
   - Consider turning off or reducing debug prints in `plc.py` (e.g. “Raw result”, “PLC values saved”) or gate them by a log level.

6. **Indexes**  
   For large tables, add indexes on:
   - `sensor_readings (device_id, timestamp)` for analysis queries.
   - `maintenance_predictions (device_id, predicted_at)` for listing by device.

7. **Frontend / dashboards**  
   The API is ready for a UI to list devices, show recent readings, and show latest predictions (e.g. GET `/devices`, `/sensors/readings/{id}`, `/devices/{id}/predictions`).

## Env vars (optional)

```env
DATABASE_URL=postgresql://user:pass@host:5432/maintenance
PLC_HOST=192.168.1.10
PLC_PORT=502
PLC_POLL_INTERVAL_SECONDS=10
DB_ECHO=false
```
