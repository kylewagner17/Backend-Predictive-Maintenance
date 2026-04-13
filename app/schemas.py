from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SensorReadingCreate(BaseModel):
    device_id: int
    reading: float
    status: str
    recorded_at: datetime | None = None


class SensorReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    reading: float
    status: str
    timestamp: datetime


class DeviceCreate(BaseModel):
    name: str


class DeviceResponse(DeviceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    status_updated_at: datetime | None = None


class TagMapCreate(BaseModel):
    tag_name: str
    device_id: int


class StatusTagMapCreate(BaseModel):
    tag_name: str
    device_id: int


class StatusTagMapResponse(StatusTagMapCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MaintenancePredictionCreate(BaseModel):
    device_id: int
    recommendation: str
    confidence: float | None = None
    details: str | None = None
    readings_snapshot: list[dict[str, Any]] | None = None


class MaintenancePredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    predicted_at: datetime
    recommendation: str
    confidence: float | None = None
    details: str | None = None
    readings_snapshot: list[dict[str, Any]] | None = None


class PushSubscriptionCreate(BaseModel):
    token: str
    device_id: int | None = None
    platform: str | None = None


class PushSubscriptionResponse(PushSubscriptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class EmailSubscriptionCreate(BaseModel):
    email: EmailStr
    device_id: int | None = None


class EmailSubscriptionResponse(EmailSubscriptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
