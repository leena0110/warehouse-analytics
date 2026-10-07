import requests
from pathlib import Path

BASE = "http://127.0.0.1:8000"

print("--- Step 1: Authentication ---")
r = requests.post(f"{BASE}/api/auth/token", data={"username": "admin", "password": "Admin@123"})
assert r.status_code == 200, f"Login failed: {r.text}"
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"[PASS] Logged in as admin. Role: {r.json().get('role')}")

print("\n--- Step 2: Warehouses ---")
r = requests.get(f"{BASE}/api/warehouses/", headers=headers)
assert r.status_code == 200, f"Get warehouses failed: {r.text}"
warehouses = r.json()
print(f"[PASS] Fetched {len(warehouses)} warehouses.")
wh_id = warehouses[0]["id"]
print(f"[PASS] Using warehouse ID: {wh_id} ({warehouses[0].get('warehouse_id', 'N/A')})")

print("\n--- Step 3: Dataset Upload ---")
csv_path = Path("data/warehouse_sample.csv")
with open(csv_path, "rb") as f:
    files = {"file": ("warehouse_sample.csv", f, "text/csv")}
    r = requests.post(
        f"{BASE}/api/datasets/upload",
        headers=headers,
        files=files,
        data={"warehouse_id": wh_id}
    )
assert r.status_code == 201, f"Upload failed: {r.text}"
dataset = r.json()
dataset_id = dataset["dataset_id"]
print(f"[PASS] Uploaded dataset ID {dataset_id}: rows={dataset.get('rows_processed')}, storage_mode={dataset.get('storage_mode')}")

print("\n--- Step 4: Run Utilization Analysis ---")
r = requests.post(f"{BASE}/api/analysis/run/{dataset_id}", headers=headers)
assert r.status_code == 201, f"Analysis failed: {r.text}"
analysis = r.json()
stats = analysis["stats"]
forecast = analysis["forecast"]
print(f"[PASS] Analysis complete! Run ID: {analysis['run_id']}")
print(f"       Total Slots: {stats['total_slots']}")
print(f"       Occupied: {stats['occupied_slots']} ({stats['utilization_pct']}%)")
print(f"       Empty: {stats['empty_slots']}")
print(f"       Blocked: {stats['blocked_slots']} ({stats['blocked_pct']}%)")
print(f"       Risk Level: {forecast['risk_level']}")
print(f"       Recommendations: {len(analysis['recommendations'])}")
print(f"       Analysis Duration: {analysis.get('duration_ms')} ms")

print("\n--- Step 5: Warehouse Slot Grid & Heatmap Data ---")
r = requests.get(f"{BASE}/api/analysis/grid/{wh_id}", headers=headers)
assert r.status_code == 200, f"Grid failed: {r.text}"
grid_data = r.json()
print(f"[PASS] Slot grid retrieved: {grid_data.get('total', 0)} slots mapped across {len(grid_data.get('zones', []))} zones.")

print("\n--- Step 6: Operational Reports & Insights ---")
# Create report
r = requests.post(f"{BASE}/api/reports/", headers=headers, json={
    "warehouse_id": wh_id,
    "title": "Aisle B Congestion Inspection",
    "content": "Heavy forklift traffic causing congestion near high velocity racks in Zone B.",
    "category": "CONGESTION",
    "severity": "HIGH"
})
assert r.status_code == 201, f"Report creation failed: {r.text}"
report_id = r.json()["id"]
print(f"[PASS] Created operational report ID: {report_id}")

# Fetch insights
r = requests.get(f"{BASE}/api/reports/insights/{wh_id}", headers=headers)
assert r.status_code == 200, f"Insights failed: {r.text}"
insights = r.json()
print(f"[PASS] Report insights generated: {insights.get('total_reports')} reports analyzed, risk level={insights.get('risk_level')}.")

print("\n--- Step 7: System Monitoring & Metrics ---")
r = requests.get(f"{BASE}/api/monitoring/health")
assert r.status_code == 200
print(f"[PASS] Health check: {r.json()['status']}")

r = requests.get(f"{BASE}/api/monitoring/metrics", headers=headers)
assert r.status_code == 200
metrics = r.json()
print(f"[PASS] Monitoring metrics: CPU={metrics.get('cpu_percent')}%, Memory={metrics.get('memory_percent')}%, Process Uptime={metrics.get('process_uptime_seconds')}s")

print("\n=======================================================")
print(">>> ALL 7 CORE WORKFLOWS VALIDATED AND FUNCTIONAL! <<<")
print("=======================================================")
