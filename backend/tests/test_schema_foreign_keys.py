"""
test_schema_foreign_keys.py — Tests for database schema, foreign key constraints,
and SQL Server 1785 multi-cascade regression prevention.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mssql, sqlite

from app.models.database import Base, init_db
from app.models.warehouse import Warehouse, Slot
from app.models.dataset import Dataset, AnalysisRun, OperationalReport
from app.models.user import User


def test_all_expected_tables_registered():
    """Verify all 6 core tables are registered in SQLAlchemy metadata."""
    expected = {
        "users",
        "warehouses",
        "slots",
        "datasets",
        "analysis_runs",
        "operational_reports",
    }
    registered = set(Base.metadata.tables.keys())
    missing = expected - registered
    assert not missing, f"Missing tables in Base.metadata: {missing}"


def test_slots_foreign_keys_compatible_with_sql_server():
    """
    SQL Server Error 1785 prevention:
    slots.warehouse_id must be CASCADE.
    slots.dataset_id must be NO ACTION (ondelete=None), NOT SET NULL or CASCADE,
    because warehouse -> datasets -> slots would form multiple cascade paths.
    """
    table = Slot.__table__
    fk_by_col = {fk.parent.name: fk for fk in table.foreign_keys}

    assert "warehouse_id" in fk_by_col, "Missing FK on slots.warehouse_id"
    assert fk_by_col["warehouse_id"].target_fullname == "warehouses.id"
    assert fk_by_col["warehouse_id"].ondelete == "CASCADE"

    assert "dataset_id" in fk_by_col, "Missing FK on slots.dataset_id"
    assert fk_by_col["dataset_id"].target_fullname == "datasets.id"
    # ondelete must NOT be SET NULL or CASCADE (prevents Error 1785)
    assert fk_by_col["dataset_id"].ondelete in (None, "NO ACTION"), (
        f"slots.dataset_id has problematic ondelete='{fk_by_col['dataset_id'].ondelete}' "
        "which causes SQL Server Error 1785 multiple cascade paths."
    )


def test_analysis_runs_foreign_keys_compatible_with_sql_server():
    """
    SQL Server Error 1785 prevention:
    analysis_runs.dataset_id is CASCADE (deleting dataset cascades to analysis runs).
    analysis_runs.warehouse_id must be NO ACTION (ondelete=None), NOT CASCADE,
    because warehouse -> datasets -> analysis_runs already provides the cascade path.
    """
    table = AnalysisRun.__table__
    fk_by_col = {fk.parent.name: fk for fk in table.foreign_keys}

    assert "dataset_id" in fk_by_col, "Missing FK on analysis_runs.dataset_id"
    assert fk_by_col["dataset_id"].target_fullname == "datasets.id"
    assert fk_by_col["dataset_id"].ondelete == "CASCADE"

    assert "warehouse_id" in fk_by_col, "Missing FK on analysis_runs.warehouse_id"
    assert fk_by_col["warehouse_id"].target_fullname == "warehouses.id"
    # ondelete must NOT be CASCADE to avoid second cascade path from warehouses
    assert fk_by_col["warehouse_id"].ondelete in (None, "NO ACTION"), (
        f"analysis_runs.warehouse_id has ondelete='{fk_by_col['warehouse_id'].ondelete}', "
        "which creates duplicate cascade paths from warehouses in SQL Server."
    )


def test_mssql_ddl_generation_no_multiple_cascades():
    """Verify generated MSSQL DDL contains safe constraint definitions."""
    dialect = mssql.dialect()

    slots_ddl = str(CreateTable(Slot.__table__).compile(dialect=dialect))
    assert "FOREIGN KEY(warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE" in slots_ddl
    assert "FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE SET NULL" not in slots_ddl
    assert "FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE CASCADE" not in slots_ddl

    analysis_ddl = str(CreateTable(AnalysisRun.__table__).compile(dialect=dialect))
    assert "FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE CASCADE" in analysis_ddl
    assert "FOREIGN KEY(warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE" not in analysis_ddl


def test_sqlite_referential_integrity_and_cascade_lifecycle():
    """
    Test complete lifecycle with SQLite foreign keys actively enforced:
    1. Creating warehouse, dataset, slots, analysis runs, reports.
    2. Deleting dataset disassociates slots (dataset_id -> None) and removes analysis runs.
    3. Deleting warehouse removes all related slots, datasets, reports.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_fk_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Create user & warehouse
        u = User(username="fk_admin", email="fk@test.local", hashed_password="pw")
        wh = Warehouse(warehouse_id="WH-TEST", name="Test Hub")
        db.add_all([u, wh])
        db.commit()

        # Create dataset
        ds = Dataset(
            filename="test.csv",
            original_filename="test.csv",
            warehouse_id=wh.id,
            uploaded_by=u.id,
        )
        db.add(ds)
        db.commit()

        # Create slot linked to warehouse & dataset
        slot = Slot(
            slot_id="S-01",
            warehouse_id=wh.id,
            dataset_id=ds.id,
            status="EMPTY",
        )
        # Create analysis run linked to dataset & warehouse
        ar = AnalysisRun(
            dataset_id=ds.id,
            warehouse_id=wh.id,
            run_by=u.id,
            utilization_pct=42.0,
        )
        # Create report linked to warehouse
        rep = OperationalReport(
            warehouse_id=wh.id,
            reported_by=u.id,
            title="Inspection",
            content="All clear",
        )
        db.add_all([slot, ar, rep])
        db.commit()

        assert db.query(Slot).filter(Slot.dataset_id == ds.id).count() == 1
        assert db.query(AnalysisRun).filter(AnalysisRun.dataset_id == ds.id).count() == 1

        # Application-level dataset deletion pattern
        db.query(Slot).filter(Slot.dataset_id == ds.id).update({Slot.dataset_id: None})
        db.delete(ds)
        db.commit()

        # Slot persists with dataset_id=None
        remaining_slot = db.query(Slot).filter(Slot.slot_id == "S-01").first()
        assert remaining_slot is not None
        assert remaining_slot.dataset_id is None

        # Analysis run was cascade-deleted with dataset
        assert db.query(AnalysisRun).count() == 0

        # Warehouse deletion cascades to remaining slots and reports
        db.delete(wh)
        db.commit()

        assert db.query(Warehouse).count() == 0
        assert db.query(Slot).count() == 0
        assert db.query(OperationalReport).count() == 0

    finally:
        db.close()
