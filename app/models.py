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
    registers = relationship("PLCRegisterMap", back_populates="device")
    

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    reading = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("Device", back_populates="readings")


class PLCRegisterMap(Base):
    __tablename__ = "plc_register_map"

    id = Column(Integer, primary_key=True)
    register_address = Column(Integer, unique=True)
    device_id = Column(Integer, ForeignKey("devices.id"))

    device = relationship("Device", back_populates="registers")


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