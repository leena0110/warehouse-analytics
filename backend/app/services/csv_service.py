"""
csv_service.py — CSV parsing, validation, and slot classification.

Validates:
  - Required columns presence
  - Valid slot status values
  - Missing/null values
  - Duplicate slot IDs
  - Numeric range checks

Returns a validated DataFrame and list of validation errors.
"""

import io
import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Any
from app.core.logger import logger

# ── Constants ────────────────────────────────────────────────────────────────
REQUIRED_COLUMNS = {
    "slot_id", "warehouse_id", "zone", "row", "column", "status"
}
OPTIONAL_COLUMNS = {"capacity", "occupancy", "last_updated", "blocked_reason"}
VALID_STATUSES = {"OCCUPIED", "EMPTY", "RESERVED", "BLOCKED"}

MAX_ROWS = 50_000   # Performance guard


def validate_and_parse_csv(file_content: bytes) -> Tuple[pd.DataFrame, List[str]]:
    """
    Parse CSV bytes, validate structure and data, return (DataFrame, errors).
    DataFrame may be partial (valid rows) when errors exist.
    If errors are critical (missing required columns), returns empty DataFrame.
    """
    errors: List[str] = []

    # ── 1. Parse CSV ─────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(io.BytesIO(file_content), dtype=str)
    except Exception as exc:
        return pd.DataFrame(), [f"CSV parse error: {exc}"]

    if df.empty:
        return pd.DataFrame(), ["CSV file is empty."]

    if len(df) > MAX_ROWS:
        errors.append(f"File has {len(df)} rows; maximum is {MAX_ROWS}. Truncating.")
        df = df.head(MAX_ROWS)

    # ── 2. Normalize column names ─────────────────────────────────────────────
    df.columns = [c.strip().lower() for c in df.columns]

    # ── 3. Required columns check ─────────────────────────────────────────────
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        return pd.DataFrame(), [f"Missing required columns: {sorted(missing_cols)}"]

    # ── 4. Strip whitespace ───────────────────────────────────────────────────
    for col in df.columns:
        df[col] = df[col].str.strip() if df[col].dtype == object else df[col]

    # ── 5. Missing values in required fields ──────────────────────────────────
    for col in REQUIRED_COLUMNS:
        null_count = df[col].isna().sum() + (df[col] == "").sum()
        if null_count > 0:
            errors.append(f"Column '{col}' has {null_count} missing values.")

    # Drop rows with null required fields
    df = df.replace("", np.nan)
    df = df.dropna(subset=list(REQUIRED_COLUMNS))

    # ── 6. Normalize status ───────────────────────────────────────────────────
    df["status"] = df["status"].str.upper()
    invalid_status = ~df["status"].isin(VALID_STATUSES)
    if invalid_status.any():
        bad_vals = df.loc[invalid_status, "status"].unique().tolist()
        errors.append(f"Invalid status values: {bad_vals}. Valid: {sorted(VALID_STATUSES)}.")
        df = df[~invalid_status]

    # ── 7. Duplicate slot IDs per warehouse ───────────────────────────────────
    dup_mask = df.duplicated(subset=["slot_id", "warehouse_id"], keep="first")
    dup_count = dup_mask.sum()
    if dup_count > 0:
        errors.append(f"{dup_count} duplicate slot_id+warehouse_id combinations removed.")
        df = df[~dup_mask]

    # ── 8. Numeric validation ─────────────────────────────────────────────────
    for col in ["capacity", "occupancy"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            neg_count = (df[col] < 0).sum()
            if neg_count > 0:
                errors.append(f"Column '{col}' has {neg_count} negative values (set to 0).")
                df[col] = df[col].clip(lower=0)

    # Fill optional numeric defaults
    if "capacity" not in df.columns:
        df["capacity"] = 100.0
    else:
        df["capacity"] = df["capacity"].fillna(100.0)

    if "occupancy" not in df.columns:
        df["occupancy"] = 0.0
    else:
        df["occupancy"] = df["occupancy"].fillna(0.0)

    if "blocked_reason" not in df.columns:
        df["blocked_reason"] = None

    if "last_updated" not in df.columns:
        df["last_updated"] = None

    logger.info(f"CSV validation complete: {len(df)} valid rows, {len(errors)} warnings.")
    return df, errors


def classify_slots(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute slot utilization statistics from a validated DataFrame.
    All calculations are derived from actual data.
    """
    total = len(df)
    if total == 0:
        return _empty_stats()

    status_counts = df["status"].value_counts().to_dict()

    occupied = int(status_counts.get("OCCUPIED", 0))
    empty = int(status_counts.get("EMPTY", 0))
    reserved = int(status_counts.get("RESERVED", 0))
    blocked = int(status_counts.get("BLOCKED", 0))

    # Utilization % = Occupied / (Total - Blocked) * 100
    # This reflects actual usable capacity utilization
    usable = total - blocked
    utilization_pct = round((occupied / usable * 100) if usable > 0 else 0.0, 2)
    blocked_pct = round((blocked / total * 100) if total > 0 else 0.0, 2)

    # Zone-level breakdown
    zone_stats = {}
    if "zone" in df.columns:
        for zone, group in df.groupby("zone"):
            z_total = len(group)
            z_occ = int((group["status"] == "OCCUPIED").sum())
            z_usable = z_total - int((group["status"] == "BLOCKED").sum())
            zone_stats[str(zone)] = {
                "total": z_total,
                "occupied": z_occ,
                "empty": int((group["status"] == "EMPTY").sum()),
                "reserved": int((group["status"] == "RESERVED").sum()),
                "blocked": int((group["status"] == "BLOCKED").sum()),
                "utilization_pct": round((z_occ / z_usable * 100) if z_usable > 0 else 0.0, 2),
            }

    # Available capacity units
    available_capacity = float(df.loc[df["status"] == "EMPTY", "capacity"].sum())

    return {
        "total_slots": total,
        "occupied_slots": occupied,
        "empty_slots": empty,
        "reserved_slots": reserved,
        "blocked_slots": blocked,
        "utilization_pct": utilization_pct,
        "blocked_pct": blocked_pct,
        "available_capacity": round(available_capacity, 2),
        "zone_stats": zone_stats,
    }


def _empty_stats() -> Dict[str, Any]:
    return {
        "total_slots": 0,
        "occupied_slots": 0,
        "empty_slots": 0,
        "reserved_slots": 0,
        "blocked_slots": 0,
        "utilization_pct": 0.0,
        "blocked_pct": 0.0,
        "available_capacity": 0.0,
        "zone_stats": {},
    }
