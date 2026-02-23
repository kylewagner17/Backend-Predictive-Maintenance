import os
import threading

from fastapi import FastAPI

from app.database import engine
from app import models
from app.api import health, sensors, analysis, notifications
from app.api.devices import router as devices_router
from app.ingest.plc import plc_loop


def create_app(run_plc_loop: bool | None = None) -> FastAPI:
    """Build the FastAPI app. Set run_plc_loop=False in tests to avoid starting the PLC thread."""
    if run_plc_loop is None:
        run_plc_loop = not os.environ.get("TESTING")
    models.Base.metadata.create_all(bind=engine)
    app = FastAPI(title="Predictive Maintenance Backend")
    app.include_router(health.router)
    app.include_router(sensors.router)
    app.include_router(devices_router)
    app.include_router(analysis.router)
    app.include_router(notifications.router)
    if run_plc_loop:
        threading.Thread(target=plc_loop, daemon=True).start()
    return app


app = create_app()
