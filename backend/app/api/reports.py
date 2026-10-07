"""
reports.py — Operational reports CRUD and insights API.
"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_db, get_current_user, require_admin, require_manager_or_admin
from app.core.logger import log_event
from app.models.user import User
from app.models.dataset import OperationalReport
from app.services.ml_service import analyze_operational_insights

router = APIRouter(prefix="/api/reports", tags=["Operational Reports"])

VALID_CATEGORIES = {"CONGESTION", "EQUIPMENT", "BLOCKAGE", "SAFETY", "DELAY", "GENERAL"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class ReportCreate(BaseModel):
    warehouse_id: int
    title: str
    content: str
    category: str = "GENERAL"
    severity: str = "LOW"


class ReportOut(BaseModel):
    id: int
    warehouse_id: int
    title: str
    content: str
    category: str
    severity: str
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("/", response_model=ReportOut, status_code=201)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Create a new operational report."""
    if payload.category.upper() not in VALID_CATEGORIES:
        raise HTTPException(400, detail=f"Invalid category. Must be one of {VALID_CATEGORIES}")
    if payload.severity.upper() not in VALID_SEVERITIES:
        raise HTTPException(400, detail=f"Invalid severity. Must be one of {VALID_SEVERITIES}")

    report = OperationalReport(
        warehouse_id=payload.warehouse_id,
        reported_by=current_user.id,
        title=payload.title[:256],
        content=payload.content,
        category=payload.category.upper(),
        severity=payload.severity.upper(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    log_event("report_created", current_user.username, f"report_id={report.id}")
    return report


@router.get("/", response_model=list[ReportOut])
def list_reports(
    warehouse_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_resolved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """List operational reports with filters and pagination."""
    q = db.query(OperationalReport)
    if warehouse_id:
        q = q.filter(OperationalReport.warehouse_id == warehouse_id)
    if category:
        q = q.filter(OperationalReport.category == category.upper())
    if severity:
        q = q.filter(OperationalReport.severity == severity.upper())
    if is_resolved is not None:
        q = q.filter(OperationalReport.is_resolved == is_resolved)

    offset = (page - 1) * page_size
    return q.order_by(OperationalReport.created_at.desc()).offset(offset).limit(page_size).all()


@router.get("/insights/{warehouse_id}")
def get_insights(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """
    Analyze operational reports for a warehouse and return structured insights.
    Uses local keyword classification (not Azure AI).
    """
    reports = db.query(OperationalReport).filter(
        OperationalReport.warehouse_id == warehouse_id
    ).order_by(OperationalReport.created_at.desc()).limit(100).all()

    report_dicts = [
        {
            "title": r.title,
            "content": r.content,
            "category": r.category,
            "severity": r.severity,
        }
        for r in reports
    ]
    return analyze_operational_insights(report_dicts)


@router.put("/{report_id}/resolve")
def resolve_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Mark a report as resolved."""
    report = db.query(OperationalReport).filter(OperationalReport.id == report_id).first()
    if not report:
        raise HTTPException(404, detail="Report not found.")
    report.is_resolved = True
    report.resolved_at = datetime.now(timezone.utc)
    db.commit()
    log_event("report_resolved", current_user.username, f"report_id={report_id}")
    return {"message": "Report resolved."}


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a report (admin only)."""
    report = db.query(OperationalReport).filter(OperationalReport.id == report_id).first()
    if not report:
        raise HTTPException(404, detail="Report not found.")
    db.delete(report)
    db.commit()
    log_event("report_deleted", current_user.username, f"report_id={report_id}")
