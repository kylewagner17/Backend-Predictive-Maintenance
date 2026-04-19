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
    """DINT/Bool-style outputs: classic PM mode uses 0/1/2 per recommendation; OP300 mode uses 0/1 per tag."""

    __tablename__ = "plc_status_tag_map"

    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    device = relationship("Device", back_populates="status_tag_maps")


class Op300ProcessState(Base):
    """Singleton row (id=1) holding consecutive-failure tracking between OP300 counter polls."""

    __tablename__ = "op300_process_state"

    id = Column(Integer, primary_key=True, index=True)
    consecutive_unsuccessful = Column(Integer, nullable=False, default=0)
    prev_success_acc = Column(Float, nullable=True)
    prev_unsuccess_acc = Column(Float, nullable=True)


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
