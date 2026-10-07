"""
conftest.py — Test fixtures: in-memory SQLite database, test client, seeded users.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.database import Base
from app.core.security import hash_password, get_db
from app.models.user import User
from app.models.warehouse import Warehouse

# ── In-memory test database ───────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_warehouse.db"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables and seed test users once per test session."""
    from app.models import user, warehouse, slot, dataset, analysis  # register models
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        # Create test admin
        if not db.query(User).filter(User.username == "test_admin").first():
            db.add(User(
                username="test_admin",
                email="admin@test.local",
                hashed_password=hash_password("Admin@123"),
                full_name="Test Admin",
                role="ADMIN",
                is_active=True,
            ))
        # Create test manager
        if not db.query(User).filter(User.username == "test_manager").first():
            db.add(User(
                username="test_manager",
                email="manager@test.local",
                hashed_password=hash_password("Manager@123"),
                full_name="Test Manager",
                role="WAREHOUSE_MANAGER",
                is_active=True,
            ))
        # Create test warehouse
        if not db.query(Warehouse).filter(Warehouse.warehouse_id == "TEST-WH-001").first():
            db.add(Warehouse(
                warehouse_id="TEST-WH-001",
                name="Test Warehouse",
                location="Test City",
            ))
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    """Return a valid JWT token for the test admin."""
    response = client.post(
        "/api/auth/token",
        data={"username": "test_admin", "password": "Admin@123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def manager_token(client):
    """Return a valid JWT token for the test manager."""
    response = client.post(
        "/api/auth/token",
        data={"username": "test_manager", "password": "Manager@123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def manager_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}
