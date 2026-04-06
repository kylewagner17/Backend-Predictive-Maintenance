import os
import threading

from fastapi import FastAPI

from app.database import SessionLocal, engine
from app import models
from app.api import health, sensors, analysis, notifications
from app.api.devices import router as devices_router
from app.ingest.plc import plc_loop
from app.ingest.synthetic import synthetic_loop


def create_app(run_plc_loop: bool | None = None) -> FastAPI:
    """
    Build the FastAPI app.
    - Tests: pass run_plc_loop=False (default when TESTING is set to any value in conftest).
    - TESTING=1: SQLite POC DB, seed demo devices, synthetic readings + console analysis (no PLC).
    - Otherwise: PLC poll thread when run_plc_loop is True.
    """
    if run_plc_loop is None:
        run_plc_loop = not os.environ.get("TESTING")
    models.Base.metadata.create_all(bind=engine)
    testing = os.environ.get("TESTING") == "1"
    if testing:
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
    if testing:
        threading.Thread(target=synthetic_loop, daemon=True).start()
    elif run_plc_loop:
        threading.Thread(target=plc_loop, daemon=True).start()
    return app


app = create_app()
