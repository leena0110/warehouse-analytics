"""
warehouses.py — Warehouse CRUD API.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_db, get_current_user, require_admin, require_manager_or_admin
from app.core.logger import log_event
from app.models.user import User
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/warehouses", tags=["Warehouses"])


class WarehouseCreate(BaseModel):
    warehouse_id: str
    name: str
    location: Optional[str] = None
    description: Optional[str] = None


class WarehouseOut(BaseModel):
    id: int
    warehouse_id: str
    name: str
    location: Optional[str]
    description: Optional[str]
    total_rows: int
    total_columns: int
    created_at: datetime

    class Config:
        from_attributes = True


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


@router.post("/", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new warehouse record (admin only)."""
    if db.query(Warehouse).filter(Warehouse.warehouse_id == payload.warehouse_id).first():
        raise HTTPException(409, detail=f"Warehouse '{payload.warehouse_id}' already exists.")
    wh = Warehouse(**payload.model_dump())
    db.add(wh)
    db.commit()
    db.refresh(wh)
    log_event("warehouse_created", current_user.username, f"wh={wh.warehouse_id}")
    return wh


@router.get("/", response_model=list[WarehouseOut])
def list_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """List all warehouses."""
    return db.query(Warehouse).all()


@router.get("/{warehouse_id}", response_model=WarehouseOut)
def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise HTTPException(404, detail="Warehouse not found.")
    return wh


@router.put("/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update warehouse metadata (admin only)."""
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise HTTPException(404, detail="Warehouse not found.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(wh, k, v)
    db.commit()
    db.refresh(wh)
    log_event("warehouse_updated", current_user.username, f"wh_id={warehouse_id}")
    return wh


@router.delete("/{warehouse_id}", status_code=204)
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a warehouse and all its data (admin only)."""
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise HTTPException(404, detail="Warehouse not found.")
    db.delete(wh)
    db.commit()
    log_event("warehouse_deleted", current_user.username, f"wh_id={warehouse_id}")
