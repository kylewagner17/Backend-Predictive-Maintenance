from datetime import datetime

from pydantic import BaseModel, EmailStr

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


class TagMapCreate(BaseModel):
    tag_name: str
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


class PushSubscriptionCreate(BaseModel):
    token: str
    device_id: int | None = None  # None = all devices
    platform: str | None = None  # "ios" | "android"


class PushSubscriptionResponse(PushSubscriptionCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSubscriptionCreate(BaseModel):
    email: EmailStr
    device_id: int | None = None  # None = all devices


class EmailSubscriptionResponse(EmailSubscriptionCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


