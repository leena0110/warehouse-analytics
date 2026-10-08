"""
test_api.py — Integration tests for warehouse, dataset, and analysis API endpoints.
"""

import io
import pytest


# ── Valid test CSV ────────────────────────────────────────────────────────────
TEST_CSV = b"""slot_id,warehouse_id,zone,row,column,status,capacity,occupancy
T001,TEST-WH-001,A,A,1,OCCUPIED,1000,800
T002,TEST-WH-001,A,A,2,EMPTY,1000,0
T003,TEST-WH-001,A,A,3,RESERVED,1000,0
T004,TEST-WH-001,A,A,4,BLOCKED,1000,0
T005,TEST-WH-001,B,B,1,OCCUPIED,500,450
T006,TEST-WH-001,B,B,2,OCCUPIED,500,300
T007,TEST-WH-001,B,B,3,EMPTY,500,0
T008,TEST-WH-001,B,B,4,EMPTY,500,0
"""


# ── Warehouse API tests ───────────────────────────────────────────────────────

def test_list_warehouses_requires_auth(client):
    """Unauthenticated request to warehouses should return 401."""
    response = client.get("/api/warehouses/")
    assert response.status_code == 401


def test_list_warehouses_manager(client, manager_headers):
    """Authenticated manager can list warehouses."""
    response = client.get("/api/warehouses/", headers=manager_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_warehouse_admin(client, admin_headers):
    """Admin can create a new warehouse."""
    response = client.post(
        "/api/warehouses/",
        json={"warehouse_id": "API-TEST-WH", "name": "API Test Warehouse"},
        headers=admin_headers,
    )
    assert response.status_code in (201, 409)  # 409 if already exists from prev run


def test_create_warehouse_manager_forbidden(client, manager_headers):
    """Manager cannot create warehouses."""
    response = client.post(
        "/api/warehouses/",
        json={"warehouse_id": "HACK-WH", "name": "Hack Attempt"},
        headers=manager_headers,
    )
    assert response.status_code == 403


# ── Dataset upload tests ──────────────────────────────────────────────────────

def _get_warehouse_id(client, manager_headers):
    warehouses = client.get("/api/warehouses/", headers=manager_headers).json()
    return warehouses[0]["id"] if warehouses else None


def test_upload_dataset_admin(client, admin_headers, manager_headers):
    """Admin can upload a valid CSV dataset."""
    wh_id = _get_warehouse_id(client, manager_headers)
    assert wh_id is not None, "Need at least one warehouse"

    response = client.post(
        "/api/datasets/upload",
        data={"warehouse_id": str(wh_id)},
        files={"file": ("test_data.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers={"Authorization": admin_headers["Authorization"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rows_processed"] == 8


def test_upload_dataset_manager_forbidden(client, manager_headers):
    """Manager cannot upload datasets."""
    wh_id = _get_warehouse_id(client, manager_headers)
    response = client.post(
        "/api/datasets/upload",
        data={"warehouse_id": str(wh_id or 1)},
        files={"file": ("test.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers={"Authorization": manager_headers["Authorization"]},
    )
    assert response.status_code == 403


def test_upload_non_csv_rejected(client, admin_headers, manager_headers):
    """Non-CSV file should be rejected with 400."""
    wh_id = _get_warehouse_id(client, manager_headers)
    response = client.post(
        "/api/datasets/upload",
        data={"warehouse_id": str(wh_id or 1)},
        files={"file": ("data.xlsx", io.BytesIO(b"binary"), "application/vnd.ms-excel")},
        headers={"Authorization": admin_headers["Authorization"]},
    )
    assert response.status_code == 400


def test_upload_invalid_csv_rejected(client, admin_headers, manager_headers):
    """CSV with missing required columns should be rejected with 422."""
    wh_id = _get_warehouse_id(client, manager_headers)
    bad_csv = b"col1,col2\nval1,val2\n"
    response = client.post(
        "/api/datasets/upload",
        data={"warehouse_id": str(wh_id or 1)},
        files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
        headers={"Authorization": admin_headers["Authorization"]},
    )
    assert response.status_code == 422


# ── Analysis API tests ────────────────────────────────────────────────────────

def test_list_datasets_authenticated(client, manager_headers):
    """Authenticated manager can list datasets."""
    response = client.get("/api/datasets/", headers=manager_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_run_analysis_on_uploaded_dataset(client, admin_headers, manager_headers):
    """Admin can trigger analysis on an uploaded dataset."""
    # Get first processed dataset
    datasets = client.get("/api/datasets/", headers=manager_headers).json()
    processed = [d for d in datasets if d["status"] == "PROCESSED"]
    if not processed:
        pytest.skip("No processed datasets available for analysis test")

    dataset_id = processed[0]["id"]
    response = client.post(f"/api/analysis/run/{dataset_id}", headers=admin_headers)
    assert response.status_code == 201
    data = response.json()
    assert "stats" in data
    assert "forecast" in data
    assert "recommendations" in data
    assert data["stats"]["total_slots"] > 0
    assert 0 <= data["stats"]["utilization_pct"] <= 100


def test_analysis_manager_cannot_trigger(client, manager_headers):
    """Manager cannot trigger analysis (admin only)."""
    response = client.post("/api/analysis/run/999", headers=manager_headers)
    assert response.status_code == 403


def test_latest_analysis_zone_stats_nested_in_stats(client, admin_headers, manager_headers):
    """
    Regression test: GET /api/analysis/latest/{id} must return zone_stats
    nested inside stats{}, not at the top level.
    Fixes: dashboard Zone Utilization chart showing 'No zones'.
    """
    # Ensure at least one processed dataset and analysis run exist
    datasets = client.get("/api/datasets/", headers=manager_headers).json()
    processed = [d for d in datasets if d["status"] == "PROCESSED"]
    if not processed:
        pytest.skip("No processed datasets — run upload test first")

    dataset_id = processed[0]["id"]
    # Run analysis to guarantee a fresh run exists
    run_resp = client.post(f"/api/analysis/run/{dataset_id}", headers=admin_headers)
    assert run_resp.status_code == 201

    # Identify warehouse id
    warehouses = client.get("/api/warehouses/", headers=manager_headers).json()
    assert warehouses, "No warehouses found"
    wh_id = warehouses[0]["id"]

    # Fetch latest analysis
    resp = client.get(f"/api/analysis/latest/{wh_id}", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()

    # zone_stats must be nested inside stats, not at top level
    assert "stats" in data, "Response must contain 'stats' key"
    stats = data["stats"]
    assert "zone_stats" in stats, (
        "stats.zone_stats is missing — zone_stats must be nested inside stats{}, "
        "not returned at the top level of the response"
    )
    assert isinstance(stats["zone_stats"], dict), "stats.zone_stats must be a dict"
    assert len(stats["zone_stats"]) > 0, "stats.zone_stats must not be empty when zone data exists"

    # Verify zone_stats values have expected shape
    for zone_name, zone_data in stats["zone_stats"].items():
        assert isinstance(zone_name, str), "Zone keys must be strings"
        assert "total" in zone_data, f"Zone {zone_name} missing 'total'"
        assert "occupied" in zone_data, f"Zone {zone_name} missing 'occupied'"
        assert "utilization_pct" in zone_data, f"Zone {zone_name} missing 'utilization_pct'"
        assert 0 <= zone_data["utilization_pct"] <= 100, f"Zone {zone_name} utilization_pct out of range"

    # Verify top-level KPI fields are still in stats
    for field in ("total_slots", "occupied_slots", "empty_slots", "reserved_slots",
                  "blocked_slots", "utilization_pct", "available_capacity"):
        assert field in stats, f"stats.{field} is missing"


def test_grid_endpoint_authenticated(client, manager_headers):
    """Grid endpoint accessible by manager, returns grid structure."""
    warehouses = client.get("/api/warehouses/", headers=manager_headers).json()
    if not warehouses:
        pytest.skip("No warehouses")
    wh_id = warehouses[0]["id"]
    response = client.get(f"/api/analysis/grid/{wh_id}", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "grid" in data
    assert "total" in data


# ── Monitoring ────────────────────────────────────────────────────────────────

def test_metrics_requires_auth(client):
    response = client.get("/api/monitoring/metrics")
    assert response.status_code == 401


def test_metrics_authenticated(client, manager_headers):
    response = client.get("/api/monitoring/metrics", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "counts" in data
    assert "uptime_seconds" in data
