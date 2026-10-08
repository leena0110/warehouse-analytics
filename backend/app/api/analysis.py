"""
analysis.py — Analysis run trigger, slot retrieval, grid, and dashboard API.
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_db, get_current_user, require_admin, require_manager_or_admin
from app.core.logger import log_event, log_error
from app.models.user import User
from app.models.warehouse import Warehouse, Slot
from app.models.dataset import Dataset, AnalysisRun
from app.services.csv_service import classify_slots
from app.services.ml_service import forecast_utilization, generate_recommendations, analyze_operational_insights

import pandas as pd

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalysisRunOut(BaseModel):
    id: int
    dataset_id: int
    warehouse_id: int
    total_slots: int
    occupied_slots: int
    empty_slots: int
    reserved_slots: int
    blocked_slots: int
    utilization_pct: float
    blocked_pct: float
    available_capacity: float
    risk_level: Optional[str]
    run_at: datetime
    duration_ms: Optional[int]
    success: bool

    class Config:
        from_attributes = True


class SlotOut(BaseModel):
    id: int
    slot_id: str
    zone: Optional[str]
    row: Optional[str]
    column: Optional[int]
    status: str
    capacity: float
    occupancy: float
    blocked_reason: Optional[str]

    class Config:
        from_attributes = True


# ── Trigger analysis ──────────────────────────────────────────────────────────

@router.post("/run/{dataset_id}", status_code=201)
def run_analysis(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Trigger a full analysis on an uploaded dataset.
    Computes utilization, ML forecast, and recommendations.
    """
    log_event("analysis_start", current_user.username, f"dataset_id={dataset_id}")
    start_ms = int(time.time() * 1000)

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, detail="Dataset not found.")
    if dataset.status not in ("PROCESSED", "UPLOADED"):
        raise HTTPException(400, detail=f"Dataset status is '{dataset.status}'. Cannot analyze.")

    # Fetch slots
    slots = db.query(Slot).filter(Slot.dataset_id == dataset_id).all()
    if not slots:
        raise HTTPException(400, detail="No slots found for this dataset. Was it processed?")

    # Build DataFrame from DB slots (avoid re-reading file for analysis)
    df = pd.DataFrame([{
        "slot_id": s.slot_id,
        "status": s.status,
        "zone": s.zone,
        "row": s.row,
        "column": s.column,
        "capacity": s.capacity,
        "occupancy": s.occupancy,
    } for s in slots])

    # Compute stats
    stats = classify_slots(df)

    # Historical utilization for forecasting
    historical = [
        r.utilization_pct
        for r in db.query(AnalysisRun)
            .filter(AnalysisRun.warehouse_id == dataset.warehouse_id)
            .order_by(AnalysisRun.run_at)
            .all()
    ]

    # ML Forecast
    forecast = forecast_utilization(historical, stats)

    # Recommendations
    recommendations = generate_recommendations(stats, forecast)

    # Duration
    duration_ms = int(time.time() * 1000) - start_ms

    # Persist AnalysisRun
    run = AnalysisRun(
        dataset_id=dataset_id,
        warehouse_id=dataset.warehouse_id,
        run_by=current_user.id,
        total_slots=stats["total_slots"],
        occupied_slots=stats["occupied_slots"],
        empty_slots=stats["empty_slots"],
        reserved_slots=stats["reserved_slots"],
        blocked_slots=stats["blocked_slots"],
        utilization_pct=stats["utilization_pct"],
        available_capacity=stats["available_capacity"],
        blocked_pct=stats["blocked_pct"],
        forecast_json=json.dumps(forecast),
        risk_level=forecast["risk_level"],
        recommendations_json=json.dumps(recommendations),
        insights_json=json.dumps(stats.get("zone_stats", {})),
        run_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        success=True,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    log_event("analysis_complete", current_user.username,
              f"run_id={run.id} util={stats['utilization_pct']}% duration={duration_ms}ms")

    return {
        "run_id": run.id,
        "stats": stats,
        "forecast": forecast,
        "recommendations": recommendations,
        "duration_ms": duration_ms,
    }


# ── Latest analysis for warehouse ─────────────────────────────────────────────

@router.get("/latest/{warehouse_id}")
def get_latest_analysis(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Get the most recent analysis run for a warehouse."""
    run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.warehouse_id == warehouse_id, AnalysisRun.success == True)
        .order_by(AnalysisRun.run_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(404, detail="No analysis runs found for this warehouse.")

    return {
        "run_id": run.id,
        "stats": {
            "total_slots": run.total_slots,
            "occupied_slots": run.occupied_slots,
            "empty_slots": run.empty_slots,
            "reserved_slots": run.reserved_slots,
            "blocked_slots": run.blocked_slots,
            "utilization_pct": run.utilization_pct,
            "available_capacity": run.available_capacity,
            "blocked_pct": run.blocked_pct,
            "zone_stats": json.loads(run.insights_json) if run.insights_json else {},
        },
        "forecast": json.loads(run.forecast_json) if run.forecast_json else None,
        "recommendations": json.loads(run.recommendations_json) if run.recommendations_json else [],
        "risk_level": run.risk_level,
        "run_at": run.run_at.isoformat(),
        "duration_ms": run.duration_ms,
    }


# ── Analysis history ──────────────────────────────────────────────────────────

@router.get("/history/{warehouse_id}", response_model=list[AnalysisRunOut])
def get_analysis_history(
    warehouse_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Get analysis run history for a warehouse."""
    runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.warehouse_id == warehouse_id)
        .order_by(AnalysisRun.run_at.desc())
        .limit(limit)
        .all()
    )
    return runs


# ── Warehouse grid / digital twin ─────────────────────────────────────────────

@router.get("/grid/{warehouse_id}")
def get_warehouse_grid(
    warehouse_id: int,
    dataset_id: Optional[int] = Query(None),
    zone_filter: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """
    Return grid representation of warehouse slots.
    Each slot includes position, status, capacity, and occupancy.
    Supports filtering by zone and status.
    """
    q = db.query(Slot).filter(Slot.warehouse_id == warehouse_id)

    if dataset_id:
        q = q.filter(Slot.dataset_id == dataset_id)
    else:
        # Use latest dataset
        latest_ds = (
            db.query(Dataset)
            .filter(Dataset.warehouse_id == warehouse_id, Dataset.status == "PROCESSED")
            .order_by(Dataset.uploaded_at.desc())
            .first()
        )
        if latest_ds:
            q = q.filter(Slot.dataset_id == latest_ds.id)

    if zone_filter:
        q = q.filter(Slot.zone == zone_filter)
    if status_filter:
        q = q.filter(Slot.status == status_filter.upper())

    slots = q.all()
    if not slots:
        return {"grid": [], "zones": [], "total": 0}

    # Group by zone → row → column
    grid_data = {}
    zones = set()
    for s in slots:
        zone = s.zone or "DEFAULT"
        row = s.row or "A"
        zones.add(zone)
        if zone not in grid_data:
            grid_data[zone] = {}
        if row not in grid_data[zone]:
            grid_data[zone][row] = []
        grid_data[zone][row].append({
            "slot_id": s.slot_id,
            "col": s.column or 0,
            "status": s.status,
            "capacity": s.capacity,
            "occupancy": s.occupancy,
            "blocked_reason": s.blocked_reason,
        })

    # Sort rows and columns
    structured = []
    for zone in sorted(grid_data.keys()):
        zone_rows = []
        for row in sorted(grid_data[zone].keys()):
            zone_rows.append({
                "row": row,
                "slots": sorted(grid_data[zone][row], key=lambda x: x["col"]),
            })
        structured.append({"zone": zone, "rows": zone_rows})

    return {
        "grid": structured,
        "zones": sorted(list(zones)),
        "total": len(slots),
    }


# ── Slots list (paginated) ────────────────────────────────────────────────────

@router.get("/slots/{warehouse_id}", response_model=list[SlotOut])
def get_slots(
    warehouse_id: int,
    dataset_id: Optional[int] = Query(None),
    zone: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Paginated slot listing with optional filters."""
    q = db.query(Slot).filter(Slot.warehouse_id == warehouse_id)
    if dataset_id:
        q = q.filter(Slot.dataset_id == dataset_id)
    if zone:
        q = q.filter(Slot.zone == zone)
    if status:
        q = q.filter(Slot.status == status.upper())

    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()
