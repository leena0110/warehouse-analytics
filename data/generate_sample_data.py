"""
generate_sample_data.py — Generates a realistic synthetic warehouse dataset.

This script creates a reproducible CSV file with warehouse slot data.
The data is clearly labeled as SYNTHETIC.

Usage: python data/generate_sample_data.py
"""

import csv
import random
import os
from datetime import datetime, timedelta, timezone

# ── Reproducible seed ─────────────────────────────────────────────────────────
random.seed(42)

# ── Configuration ─────────────────────────────────────────────────────────────
WAREHOUSE_ID = "WH-001"
ZONES = ["A", "B", "C", "D", "E"]
ROWS_PER_ZONE = 8
COLS_PER_ROW = 10

# Status distribution to make it interesting
STATUS_WEIGHTS = {
    "OCCUPIED": 0.52,
    "EMPTY": 0.28,
    "RESERVED": 0.12,
    "BLOCKED": 0.08,
}

BLOCKED_REASONS = [
    "Maintenance scheduled",
    "Equipment obstruction",
    "Safety inspection pending",
    "Floor damage",
    "Fire exit clearance",
    "Pest control area",
    None, None, None,  # Most blocked slots have no text reason
]

ROW_LABELS = [chr(65 + i) for i in range(ROWS_PER_ZONE)]  # A–H

BASE_DATE = datetime(2026, 9, 1, tzinfo=timezone.utc)


def weighted_status():
    r = random.random()
    cumulative = 0.0
    for status, weight in STATUS_WEIGHTS.items():
        cumulative += weight
        if r <= cumulative:
            return status
    return "EMPTY"


def generate_slots():
    slots = []
    for zone in ZONES:
        for row_idx, row_label in enumerate(ROW_LABELS):
            for col in range(1, COLS_PER_ROW + 1):
                slot_id = f"{WAREHOUSE_ID}-{zone}{row_label}{col:02d}"
                status = weighted_status()

                # Capacity: 500–2000 units
                capacity = random.choice([500, 750, 1000, 1500, 2000])

                # Occupancy depends on status
                if status == "OCCUPIED":
                    occupancy = round(random.uniform(0.5, 1.0) * capacity, 1)
                elif status == "RESERVED":
                    occupancy = 0.0
                elif status == "BLOCKED":
                    occupancy = 0.0
                else:  # EMPTY
                    occupancy = 0.0

                # Last updated: random within last 30 days
                days_ago = random.randint(0, 30)
                last_updated = (BASE_DATE + timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

                blocked_reason = None
                if status == "BLOCKED":
                    blocked_reason = random.choice(BLOCKED_REASONS)

                slots.append({
                    "slot_id": slot_id,
                    "warehouse_id": WAREHOUSE_ID,
                    "zone": zone,
                    "row": row_label,
                    "column": col,
                    "status": status,
                    "capacity": capacity,
                    "occupancy": occupancy,
                    "last_updated": last_updated,
                    "blocked_reason": blocked_reason or "",
                })
    return slots


def main():
    slots = generate_slots()
    output_path = os.path.join(os.path.dirname(__file__), "warehouse_sample.csv")

    fieldnames = [
        "slot_id", "warehouse_id", "zone", "row", "column",
        "status", "capacity", "occupancy", "last_updated", "blocked_reason"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(slots)

    # Summary
    total = len(slots)
    status_counts = {}
    for s in slots:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    print(f"\n[OK] Generated SYNTHETIC warehouse dataset: {output_path}")
    print(f"   Total slots:  {total}")
    for status, count in status_counts.items():
        pct = count / total * 100
        print(f"   {status:<12}: {count:4d} ({pct:.1f}%)")
    print(f"\n   Zones:        {', '.join(ZONES)}")
    print(f"   Rows/zone:    {ROWS_PER_ZONE}")
    print(f"   Cols/row:     {COLS_PER_ROW}")
    print(f"\n   NOTE: This data is entirely synthetic and generated for demo purposes.")


if __name__ == "__main__":
    main()
