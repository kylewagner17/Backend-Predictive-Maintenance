from fastapi import FastAPI
from app.database import engine
from app import models
from app.api import health, sensors, analysis, notifications
from app.api.devices import router as devices_router
from app.ingest.plc import plc_loop
import threading

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Predictive Maintenance Backend")

app.include_router(health.router)
app.include_router(sensors.router)
app.include_router(devices_router)
app.include_router(analysis.router)
app.include_router(notifications.router)

threading.Thread(target=plc_loop, daemon=True).start()
