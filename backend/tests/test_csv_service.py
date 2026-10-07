"""
test_csv_service.py — Tests for CSV validation and slot classification.
"""

import pytest
import pandas as pd
from app.services.csv_service import validate_and_parse_csv, classify_slots


# ── CSV Validation Tests ──────────────────────────────────────────────────────

VALID_CSV = b"""slot_id,warehouse_id,zone,row,column,status,capacity,occupancy
S001,WH-001,A,A,1,OCCUPIED,1000,750
S002,WH-001,A,A,2,EMPTY,1000,0
S003,WH-001,A,A,3,RESERVED,1000,0
S004,WH-001,A,A,4,BLOCKED,1000,0
S005,WH-001,B,A,1,OCCUPIED,500,400
"""

def test_valid_csv_parses_correctly():
    """Valid CSV should parse with no errors and correct row count."""
    df, errors = validate_and_parse_csv(VALID_CSV)
    assert not df.empty
    assert len(df) == 5
    # Status should be upper-cased strings
    assert set(df["status"]) == {"OCCUPIED", "EMPTY", "RESERVED", "BLOCKED"}


def test_missing_required_column():
    """CSV missing required column should return empty DataFrame with error."""
    bad_csv = b"""slot_id,warehouse_id,zone,row
S001,WH-001,A,A
"""
    df, errors = validate_and_parse_csv(bad_csv)
    assert df.empty
    assert any("Missing required columns" in e for e in errors)


def test_invalid_status_rejected():
    """Rows with invalid status values should be filtered out."""
    csv_data = b"""slot_id,warehouse_id,zone,row,column,status
S001,WH-001,A,A,1,OCCUPIED
S002,WH-001,A,A,2,INVALID_STATUS
S003,WH-001,A,A,3,EMPTY
"""
    df, errors = validate_and_parse_csv(csv_data)
    assert len(df) == 2  # invalid row removed
    assert any("Invalid status" in e for e in errors)


def test_duplicate_slot_ids_removed():
    """Duplicate slot_id + warehouse_id pairs should be deduplicated."""
    csv_data = b"""slot_id,warehouse_id,zone,row,column,status
S001,WH-001,A,A,1,OCCUPIED
S001,WH-001,A,A,1,EMPTY
S002,WH-001,A,A,2,EMPTY
"""
    df, errors = validate_and_parse_csv(csv_data)
    assert len(df) == 2
    assert any("duplicate" in e.lower() for e in errors)


def test_empty_csv_returns_error():
    """Empty CSV file should return error."""
    df, errors = validate_and_parse_csv(b"")
    assert df.empty
    # Should have either parse error or empty error


def test_missing_values_handled():
    """CSV with missing required values should report them."""
    csv_data = b"""slot_id,warehouse_id,zone,row,column,status
S001,WH-001,A,A,1,
S002,WH-001,A,A,2,EMPTY
"""
    df, errors = validate_and_parse_csv(csv_data)
    # Row with missing status should be dropped
    assert len(df) == 1


# ── Classification Tests ──────────────────────────────────────────────────────

def test_classify_slots_utilization():
    """Utilization pct = occupied / (total - blocked) * 100."""
    df, _ = validate_and_parse_csv(VALID_CSV)
    stats = classify_slots(df)
    # 2 OCCUPIED out of 4 usable (5 total - 1 blocked)
    assert stats["total_slots"] == 5
    assert stats["occupied_slots"] == 2
    assert stats["empty_slots"] == 1
    assert stats["reserved_slots"] == 1
    assert stats["blocked_slots"] == 1
    expected_util = round(2 / 4 * 100, 2)  # 50.0
    assert stats["utilization_pct"] == expected_util


def test_classify_slots_zero_slots():
    """Empty DataFrame should return zero stats, no exceptions."""
    stats = classify_slots(pd.DataFrame())
    assert stats["total_slots"] == 0
    assert stats["utilization_pct"] == 0.0


def test_classify_zone_breakdown():
    """Zone breakdown should be computed per zone."""
    df, _ = validate_and_parse_csv(VALID_CSV)
    stats = classify_slots(df)
    assert "zone_stats" in stats
    assert "A" in stats["zone_stats"]
    assert "B" in stats["zone_stats"]


def test_classify_all_blocked():
    """If all slots are blocked, utilization should be 0%."""
    csv_data = b"""slot_id,warehouse_id,zone,row,column,status,capacity,occupancy
S001,WH-001,A,A,1,BLOCKED,1000,0
S002,WH-001,A,A,2,BLOCKED,1000,0
"""
    df, _ = validate_and_parse_csv(csv_data)
    stats = classify_slots(df)
    assert stats["utilization_pct"] == 0.0
    assert stats["blocked_pct"] == 100.0


def test_classify_all_occupied():
    """If all usable slots are occupied, utilization should be 100%."""
    csv_data = b"""slot_id,warehouse_id,zone,row,column,status,capacity,occupancy
S001,WH-001,A,A,1,OCCUPIED,1000,1000
S002,WH-001,A,A,2,OCCUPIED,1000,900
"""
    df, _ = validate_and_parse_csv(csv_data)
    stats = classify_slots(df)
    assert stats["utilization_pct"] == 100.0
