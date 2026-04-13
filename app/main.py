import os
import threading

from fastapi import FastAPI

from app.config import settings
from app.database import SessionLocal, engine
from app.device_storage import sync_tables_for_all_devices
from app import models
from app.api import health, sensors, analysis, notifications
from app.api.devices import router as devices_router
from app.industrial.logging_setup import configure_logging
from app.ingest.plc import plc_loop
from app.ingest.synthetic import synthetic_loop

_scheduler = None


def create_app(run_plc_loop: bool | None = None) -> FastAPI:
    """PLC thread off if os.environ TESTING is set (pytest) or settings.testing (POC)."""
    global _scheduler

    configure_logging(settings.log_level)

    if run_plc_loop is None:
        run_plc_loop = not os.environ.get("TESTING") and not settings.testing
    models.Base.metadata.create_all(bind=engine)
    _db = SessionLocal()
    try:
        sync_tables_for_all_devices(_db)
    finally:
        _db.close()
    if settings.testing:
        from seed_devices import ensure_demo_devices_seeded

        db = SessionLocal()
        try:
            ensure_demo_devices_seeded(db)
            print("[POC] TESTING=1: demo devices/tag maps ensured; using synthetic sensor feed.")
        finally:
            db.close()

    app = FastAPI(title="Predictive Maintenance Backend")
    app.include_router(health.router)
    app.include_router(sensors.router)
    app.include_router(devices_router)
    app.include_router(analysis.router)
    app.include_router(notifications.router)
    if settings.testing:
        threading.Thread(target=synthetic_loop, daemon=True).start()
    elif run_plc_loop:
        threading.Thread(target=plc_loop, daemon=True).start()

    if settings.scheduler_enabled and not settings.testing:
        from app.jobs.scheduler import start_scheduler

        _scheduler = start_scheduler()

    return app


app = create_app()
