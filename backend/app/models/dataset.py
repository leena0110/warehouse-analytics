"""
dataset.py — Dataset and AnalysisRun ORM models.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum, Boolean
)
from sqlalchemy.orm import relationship
from app.models.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(256), nullable=False)
    original_filename = Column(String(256), nullable=False)
    blob_url = Column(Text, nullable=True)         # Azure Blob URL or local path
    blob_name = Column(String(512), nullable=True) # Blob storage object name
    storage_mode = Column(String(16), default="local")  # "azure" | "local"
    file_size_bytes = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum("UPLOADED", "PROCESSING", "PROCESSED", "FAILED", name="dataset_status"),
        default="UPLOADED",
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="datasets")
    uploader = relationship("User")
    slots = relationship("Slot", back_populates="dataset")
    analysis_runs = relationship("AnalysisRun", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dataset id={self.id} file={self.original_filename} status={self.status}>"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    run_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Core metrics
    total_slots = Column(Integer, default=0)
    occupied_slots = Column(Integer, default=0)
    empty_slots = Column(Integer, default=0)
    reserved_slots = Column(Integer, default=0)
    blocked_slots = Column(Integer, default=0)
    utilization_pct = Column(Float, default=0.0)
    available_capacity = Column(Float, default=0.0)
    blocked_pct = Column(Float, default=0.0)

    # AI/ML forecast
    forecast_json = Column(Text, nullable=True)       # JSON: 7-day predictions
    risk_level = Column(String(16), nullable=True)    # LOW | MEDIUM | HIGH | CRITICAL
    recommendations_json = Column(Text, nullable=True) # JSON list of recommendations

    # Operational insights
    insights_json = Column(Text, nullable=True)

    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    dataset = relationship("Dataset", back_populates="analysis_runs")
    warehouse = relationship("Warehouse")
    analyst = relationship("User")

    def __repr__(self):
        return f"<AnalysisRun id={self.id} util={self.utilization_pct:.1f}%>"


class OperationalReport(Base):
    __tablename__ = "operational_reports"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    reported_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(
        Enum("CONGESTION", "EQUIPMENT", "BLOCKAGE", "SAFETY", "DELAY", "GENERAL", name="report_category"),
        default="GENERAL",
    )
    severity = Column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="report_severity"),
        default="LOW",
    )
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = Column(DateTime, nullable=True)

    warehouse = relationship("Warehouse")
    reporter = relationship("User")

    def __repr__(self):
        return f"<OperationalReport id={self.id} cat={self.category} sev={self.severity}>"
