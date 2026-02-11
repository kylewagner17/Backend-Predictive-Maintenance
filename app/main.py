from fastapi import FastAPI
from app.database import engine
from app import models
from app.api import sensors, health

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Predictive Mainenance Backend")

app.include_router(sensors.router)
app.include_router(health.router)
