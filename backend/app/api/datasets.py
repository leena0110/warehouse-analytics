"""
datasets.py — Dataset upload, listing, retrieval, deletion API.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_db, get_current_user, require_admin, require_manager_or_admin
from app.core.config import get_settings
from app.core.logger import log_event, log_error
from app.models.user import User
from app.models.warehouse import Warehouse, Slot
from app.models.dataset import Dataset
from app.services.storage_service import upload_file, delete_blob
from app.services.csv_service import validate_and_parse_csv

settings = get_settings()
router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

ALLOWED_MIME = {"text/csv", "application/csv", "text/plain"}


class DatasetOut(BaseModel):
    id: int
    original_filename: str
    warehouse_id: int
    status: str
    row_count: Optional[int]
    file_size_bytes: Optional[int]
    storage_mode: str
    blob_url: Optional[str]
    uploaded_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


@router.post("/upload", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    warehouse_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Upload a warehouse slot CSV dataset.
    - Validates file type and size
    - Validates CSV structure
    - Stores in Azure Blob Storage (or local fallback)
    - Creates Dataset record in DB
    - Processes slots immediately
    """
    log_event("dataset_upload_start", current_user.username, f"file={file.filename}")

    # ── File type validation ──────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, detail="Only CSV files are accepted.")

    # ── File size validation ──────────────────────────────────────────────────
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(413, detail=f"File exceeds {settings.max_upload_size_mb}MB limit.")
    if len(content) == 0:
        raise HTTPException(400, detail="Uploaded file is empty.")

    # ── Warehouse existence check ─────────────────────────────────────────────
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(404, detail=f"Warehouse with id={warehouse_id} not found.")

    # ── CSV validation ────────────────────────────────────────────────────────
    df, validation_errors = validate_and_parse_csv(content)
    if df.empty:
        raise HTTPException(422, detail={"errors": validation_errors, "message": "CSV validation failed."})

    # ── Storage upload ────────────────────────────────────────────────────────
    storage_result = await upload_file(content, file.filename)
    if not storage_result.success:
        log_error("storage_upload_failed", current_user.username, storage_result.error)
        raise HTTPException(500, detail="File storage failed. Please try again.")

    # ── Create Dataset record ─────────────────────────────────────────────────
    dataset = Dataset(
        filename=storage_result.blob_name,
        original_filename=file.filename,
        blob_url=storage_result.url,
        blob_name=storage_result.blob_name,
        storage_mode=storage_result.mode,
        file_size_bytes=len(content),
        row_count=len(df),
        warehouse_id=warehouse_id,
        uploaded_by=current_user.id,
        status="PROCESSING",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    # ── Process slots ─────────────────────────────────────────────────────────
    try:
        _persist_slots(db, df, warehouse, dataset)
        dataset.status = "PROCESSED"
        dataset.processed_at = datetime.now(timezone.utc)
        db.commit()
        log_event("dataset_processed", current_user.username, f"dataset_id={dataset.id} rows={len(df)}")
    except Exception as exc:
        dataset.status = "FAILED"
        dataset.error_message = str(exc)
        db.commit()
        log_error("dataset_processing_failed", current_user.username, str(exc))
        raise HTTPException(500, detail=f"Processing failed: {exc}")

    return {
        "dataset_id": dataset.id,
        "rows_processed": len(df),
        "warnings": validation_errors,
        "storage_mode": storage_result.mode,
        "message": "Dataset uploaded and processed successfully.",
    }


def _persist_slots(db, df, warehouse: Warehouse, dataset: Dataset):
    """Persist validated slot rows to the database. Replaces existing slots for dataset."""
    # Remove old slots for this warehouse/dataset
    db.query(Slot).filter(
        Slot.warehouse_id == warehouse.id,
        Slot.dataset_id == dataset.id,
    ).delete()

    slots_to_add = []
    for _, row in df.iterrows():
        slot = Slot(
            slot_id=str(row["slot_id"]),
            warehouse_id=warehouse.id,
            zone=str(row.get("zone", "")) or None,
            row=str(row.get("row", "")) or None,
            column=_safe_int(row.get("column")),
            status=str(row["status"]),
            capacity=float(row.get("capacity", 100.0) or 100.0),
            occupancy=float(row.get("occupancy", 0.0) or 0.0),
            blocked_reason=str(row["blocked_reason"]) if row.get("blocked_reason") and str(row["blocked_reason"]) != "nan" else None,
            last_updated=_parse_dt(row.get("last_updated")),
            dataset_id=dataset.id,
        )
        slots_to_add.append(slot)

    db.bulk_save_objects(slots_to_add)

    # Update warehouse dimensions
    warehouse.total_rows = df["row"].nunique()
    warehouse.total_columns = df["column"].nunique() if "column" in df.columns else 0
    db.commit()


def _safe_int(val):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _parse_dt(val):
    if not val or str(val) == "nan":
        return None
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


@router.get("/", response_model=list[DatasetOut])
def list_datasets(
    warehouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """List all datasets, optionally filtered by warehouse."""
    q = db.query(Dataset)
    if warehouse_id:
        q = q.filter(Dataset.warehouse_id == warehouse_id)
    return q.order_by(Dataset.uploaded_at.desc()).all()


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, detail="Dataset not found.")
    return dataset


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a dataset and its blob (admin only)."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(404, detail="Dataset not found.")

    if dataset.blob_name:
        await delete_blob(dataset.blob_name)

    db.delete(dataset)
    db.commit()
    log_event("dataset_deleted", current_user.username, f"dataset_id={dataset_id}")
