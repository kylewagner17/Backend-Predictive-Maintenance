from fastapi import FastAPI
from app.database import engine
from app import models
from app.ingest.plc import plc_loop
import threading

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Predictive Mainenance Backend")

threading.Thread(target=plc_loop, daemon=True).start()
