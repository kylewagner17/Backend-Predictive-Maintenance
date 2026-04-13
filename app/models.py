from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    """Current PM status lives here; per-device time-series are in ``device_{id}_*`` tables."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="OK")
    status_updated_at = Column(DateTime(timezone=True), nullable=True)

    tag_maps = relationship("PLCTagMap", back_populates="device")
    status_tag_maps = relationship("PLCStatusTagMap", back_populates="device")


class PLCTagMap(Base):
    __tablename__ = "plc_tag_map"

    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="tag_maps")


class PLCStatusTagMap(Base):
    """DINT written by backend: 0 OK, 1 INSPECT_SOON, 2 MAINTENANCE_REQUIRED."""

    __tablename__ = "plc_status_tag_map"

    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="status_tag_maps")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    platform = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
