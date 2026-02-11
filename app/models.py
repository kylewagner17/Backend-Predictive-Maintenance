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
    

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    reading = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("Device", back_populates="readings")