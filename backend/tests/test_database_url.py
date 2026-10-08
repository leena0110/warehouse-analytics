"""
test_database_url.py — Focused tests for database URL construction,
special character password handling, safe masking, and default seeding.
Uses fake/test credentials only. Never logs or leaks real credentials.
"""

from sqlalchemy.engine import URL
from app.core.config import Settings
from app.models.database import (
    build_database_url_and_connect_args,
    get_safe_db_url,
    _seed_default_warehouse,
)
from app.models.warehouse import Warehouse


def test_sqlite_fallback_default():
    """Default configuration returns SQLite without modifications."""
    cfg = Settings(database_url="sqlite:///./test.db")
    url, connect_args, is_mssql = build_database_url_and_connect_args(cfg)

    assert is_mssql is False
    assert url == "sqlite:///./test.db"
    assert connect_args.get("check_same_thread") is False


def test_discrete_settings_url_create():
    """Discrete settings produce a valid SQLAlchemy URL with ODBC Driver 18 query parameters."""
    cfg = Settings(
        sql_server="warehouseanalytics-sql.database.windows.net",
        sql_database="warehouseanalyticsdb",
        sql_user="test_admin",
        sql_password="test_password_123",
        sql_port=1433,
        sql_connection_timeout=45,
    )
    url, connect_args, is_mssql = build_database_url_and_connect_args(cfg)

    assert is_mssql is True
    assert isinstance(url, URL)
    assert url.drivername == "mssql+pyodbc"
    assert url.username == "test_admin"
    assert url.password == "test_password_123"
    assert url.host == "warehouseanalytics-sql.database.windows.net"
    assert url.port == 1433
    assert url.database == "warehouseanalyticsdb"
    assert url.query.get("driver") == "ODBC Driver 18 for SQL Server"
    assert url.query.get("Encrypt") == "yes"
    assert url.query.get("TrustServerCertificate") == "no"
    assert url.query.get("Connection Timeout") == "45"
    assert connect_args.get("timeout") == 45


def test_password_with_at_symbol():
    """Password with '@' is handled safely without string splitting errors."""
    cfg = Settings(
        sql_server="myserver.database.windows.net",
        sql_database="mydb",
        sql_user="myuser",
        sql_password="Complex@Password@With@Ats",
    )
    url, connect_args, is_mssql = build_database_url_and_connect_args(cfg)

    assert is_mssql is True
    assert isinstance(url, URL)
    assert url.password == "Complex@Password@With@Ats"
    # Safe representation must hide password
    safe_str = get_safe_db_url(url)
    assert "Complex@Password@With@Ats" not in safe_str
    assert "***" in safe_str


def test_password_with_special_characters():
    """Password with URL special characters (@ / : ? # % & ; { }) is preserved exactly."""
    special_pw = "P@ss:w/o?r#d%1&2;3{4}"
    cfg = Settings(
        sql_server="myserver.database.windows.net",
        sql_database="mydb",
        sql_user="myuser",
        sql_password=special_pw,
    )
    url, connect_args, is_mssql = build_database_url_and_connect_args(cfg)

    assert is_mssql is True
    assert isinstance(url, URL)
    assert url.password == special_pw
    safe_str = get_safe_db_url(url)
    assert special_pw not in safe_str
    assert "***" in safe_str


def test_raw_database_url_normalization_with_encoded_at():
    """Raw DATABASE_URL containing %40 in password is normalized correctly."""
    raw = (
        "mssql+pyodbc://testuser:Secr%40t123@sqlserver.database.windows.net:1433/testdb"
    )
    cfg = Settings(database_url=raw)
    url, connect_args, is_mssql = build_database_url_and_connect_args(cfg)

    assert is_mssql is True
    assert isinstance(url, URL)
    assert url.username == "testuser"
    assert url.password == "Secr@t123"
    assert url.host == "sqlserver.database.windows.net"
    assert url.database == "testdb"
    assert url.query.get("driver") == "ODBC Driver 18 for SQL Server"
    assert url.query.get("Encrypt") == "yes"
    assert url.query.get("TrustServerCertificate") == "no"


def test_safe_logging_never_exposes_secrets():
    """get_safe_db_url masks both URL objects and raw connection strings."""
    # Test with URL object
    u = URL.create(
        "mssql+pyodbc",
        username="admin",
        password="SuperSecretPassword!",
        host="myhost.database.windows.net",
        database="mydb",
    )
    safe = get_safe_db_url(u)
    assert "SuperSecretPassword!" not in safe
    assert "admin:***@" in safe

    # Test with string containing password
    raw_str = "mssql+pyodbc://admin:SuperSecretPassword!@myhost.database.windows.net/mydb"
    safe_raw = get_safe_db_url(raw_str)
    assert "SuperSecretPassword!" not in safe_raw
    assert "admin:***@" in safe_raw


def test_seed_default_warehouse_idempotent():
    """_seed_default_warehouse seeds WH-001 if missing, and does not duplicate."""
    # Run seeding function
    _seed_default_warehouse()
    from app.models.database import SessionLocal
    db = SessionLocal()
    try:
        wh = db.query(Warehouse).filter(Warehouse.warehouse_id == "WH-001").first()
        assert wh is not None
        assert wh.warehouse_id == "WH-001"
        assert bool(wh.name)

        # Calling again must not raise or create duplicate
        _seed_default_warehouse()
        count = db.query(Warehouse).filter(Warehouse.warehouse_id == "WH-001").count()
        assert count == 1
    finally:
        db.close()
