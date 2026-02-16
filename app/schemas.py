from pydantic import BaseModel
from datetime import datetime

class SensorReadingCreate(BaseModel):
    device_id: int
    reading: float
    status: str


class SensorReadingResponse(SensorReadingCreate):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True


class DeviceCreate(BaseModel):
    name: str


class DeviceResponse(DeviceCreate):
    id: int
    status: str

    class Config:
        orm_mode = True


class RegisterMapCreate(BaseModel):
    register_address: int
    device_id: int


class MaintenancePredictionCreate(BaseModel):
    device_id: int
    recommendation: str
    confidence: float | None = None
    details: str | None = None


class MaintenancePredictionResponse(MaintenancePredictionCreate):
    id: int
    predicted_at: datetime

    class Config:
        from_attributes = True


