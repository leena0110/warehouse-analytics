"""
warehouse.py — Warehouse and Slot ORM models.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Index
)
from sqlalchemy.orm import relationship
from app.models.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    total_rows = Column(Integer, default=0)
    total_columns = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    slots = relationship("Slot", back_populates="warehouse", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="warehouse", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Warehouse {self.warehouse_id}>"


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(String(64), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    zone = Column(String(16), nullable=True, index=True)
    row = Column(String(8), nullable=True, index=True)
    column = Column(Integer, nullable=True)
    status = Column(
        Enum("OCCUPIED", "EMPTY", "RESERVED", "BLOCKED", name="slot_status"),
        nullable=False,
        default="EMPTY",
        index=True,
    )
    capacity = Column(Float, default=100.0)      # max weight/volume units
    occupancy = Column(Float, default=0.0)       # current occupancy units
    blocked_reason = Column(String(256), nullable=True)
    last_updated = Column(DateTime, nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    warehouse = relationship("Warehouse", back_populates="slots")
    dataset = relationship("Dataset", back_populates="slots")

    # Composite index for performance
    __table_args__ = (
        Index("ix_slots_warehouse_zone", "warehouse_id", "zone"),
        Index("ix_slots_warehouse_status", "warehouse_id", "status"),
    )

    def __repr__(self):
        return f"<Slot {self.slot_id} status={self.status}>"
