from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="OK")

    readings = relationship("SensorReading", back_populates="device")
    tag_maps = relationship("PLCTagMap", back_populates="device")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    reading = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("Device", back_populates="readings")


class PLCTagMap(Base):
    """Maps Allen-Bradley controller tag name to a device for sensor ingest."""
    __tablename__ = "plc_tag_map"

    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="tag_maps")


class MaintenancePrediction(Base):
    """Output of analysis: predicted need for maintenance per device."""
    __tablename__ = "maintenance_predictions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), index=True)
    predicted_at = Column(DateTime, default=datetime.utcnow)
    recommendation = Column(String)  # e.g. "OK", "INSPECT_SOON", "MAINTENANCE_REQUIRED"
    confidence = Column(Float, nullable=True)  # 0–1 if your model outputs it
    details = Column(String, nullable=True)  # JSON or text summary for debugging

    device = relationship("Device", backref="predictions")


class PushSubscription(Base):
    """Stores a device push token; user gets notified when recommendation changes."""
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)  # FCM/APNs token
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    # device_id is None = subscribe to all devices; otherwise only that device
    platform = Column(String, nullable=True)  # e.g. "ios", "android" for provider choice
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailSubscription(Base):
    """Email address to notify when recommendation status changes for a device (or all)."""
    __tablename__ = "email_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    # device_id is None = all devices; otherwise only that device
    created_at = Column(DateTime, default=datetime.utcnow)