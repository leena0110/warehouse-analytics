"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.
Supports SQLite (local dev) and Azure SQL (production) with robust URL construction.
"""

import re
import time
import urllib.parse
from typing import Tuple, Union
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.logger import logger

settings = get_settings()


def build_database_url_and_connect_args(cfg: Settings) -> Tuple[Union[str, URL], dict, bool]:
    """
    Construct a robust database URL and connect_args.
    Supports:
      1. Discrete settings (sql_server, sql_database, sql_user, sql_password) using URL.create
         which safely handles passwords with special characters (@, :, /, ?, #, %, &, ;) without manual encoding.
      2. Full DATABASE_URL string (SQLite or MSSQL), normalized with required Azure SQL ODBC parameters.
    Returns: (db_url, connect_args, is_mssql)
    """
    # ── Option 1: Discrete Azure SQL settings (safest approach) ───────────────
    if cfg.sql_server and cfg.sql_database and cfg.sql_user:
        server = cfg.sql_server
        if "." not in server:
            server = f"{server}.database.windows.net"

        query_params = {
            "driver": cfg.sql_driver or "ODBC Driver 18 for SQL Server",
            "Encrypt": cfg.sql_encrypt or "yes",
            "TrustServerCertificate": cfg.sql_trust_server_certificate or "no",
            "Connection Timeout": str(cfg.sql_connection_timeout or 60),
        }
        url = URL.create(
            drivername="mssql+pyodbc",
            username=cfg.sql_user,
            password=cfg.sql_password,
            host=server,
            port=cfg.sql_port or 1433,
            database=cfg.sql_database,
            query=query_params,
        )
        connect_args = {"timeout": int(cfg.sql_connection_timeout or 60)}
        return url, connect_args, True

    # ── Option 2: SQLite database URL ─────────────────────────────────────────
    raw_url = cfg.database_url or "sqlite:///./warehouse.db"
    if raw_url.startswith("sqlite"):
        return raw_url, {"check_same_thread": False}, False

    # ── Option 3: MSSQL database URL parsing & normalization ──────────────────
    if "mssql" in raw_url:
        try:
            proto, rest = raw_url.split("://", 1)
            creds, endpoint = rest.rsplit("@", 1) if "@" in rest else ("", rest)

            user = ""
            pwd = ""
            if creds:
                parts = creds.split(":", 1)
                user = parts[0]
                pwd = urllib.parse.unquote(parts[1]) if len(parts) > 1 else ""

            if "?" in endpoint:
                hp_db, query_str = endpoint.split("?", 1)
                q_dict = dict(urllib.parse.parse_qsl(query_str))
            else:
                hp_db, q_dict = endpoint, {}

            if "/" in hp_db:
                host_port, dbname = hp_db.split("/", 1)
            else:
                host_port, dbname = hp_db, ""

            if ":" in host_port:
                host, port_str = host_port.split(":", 1)
                port = int(port_str)
            else:
                host, port = host_port, 1433

            # Ensure required Azure SQL ODBC parameters
            if "driver" not in q_dict:
                q_dict["driver"] = cfg.sql_driver or "ODBC Driver 18 for SQL Server"
            if "Encrypt" not in q_dict and "encrypt" not in q_dict:
                q_dict["Encrypt"] = cfg.sql_encrypt or "yes"
            if "TrustServerCertificate" not in q_dict and "trustservercertificate" not in q_dict:
                q_dict["TrustServerCertificate"] = cfg.sql_trust_server_certificate or "no"
            if "Connection Timeout" not in q_dict and "timeout" not in q_dict:
                q_dict["Connection Timeout"] = str(cfg.sql_connection_timeout or 60)

            url = URL.create(
                drivername=proto,
                username=user,
                password=pwd,
                host=host,
                port=port,
                database=dbname,
                query=q_dict,
            )
            connect_args = {"timeout": int(q_dict.get("Connection Timeout", 60))}
            return url, connect_args, True
        except Exception as exc:
            logger.warning(f"Could not normalize MSSQL URL via URL.create: {exc}. Using raw URL.")
            return raw_url, {"timeout": 60}, True

    return raw_url, {}, False


db_url, connect_args, is_mssql = build_database_url_and_connect_args(settings)


def get_safe_db_url(url: Union[str, URL] = db_url) -> str:
    """Return a masked connection string safe for logging (never shows credentials)."""
    if isinstance(url, URL):
        return url.render_as_string(hide_password=True)
    if "sqlite" in str(url):
        return "sqlite (local file)"
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", str(url))


# ── Engine configuration ──────────────────────────────────────────────────────
engine_kwargs = {
    "connect_args": connect_args,
    "echo": settings.debug,
    "pool_pre_ping": True,       # Detect and drop stale/broken connections
}

if is_mssql:
    # Production connection pool settings for Azure App Service & Azure SQL
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,    # Recycle connections after 30 min (Azure idle timeout is 4-30 min)
        "pool_timeout": 30,
    })
else:
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(db_url, **engine_kwargs)

# Enable WAL mode for SQLite (better local concurrency)
if not is_mssql and str(db_url).startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db(max_retries: int = 3, retry_delay: int = 5):
    """
    Create all tables and seed initial data.
    Includes retry logic with backoff for cloud databases (e.g. Azure SQL wake-up).
    """
    from app.models import user, warehouse, slot, dataset, analysis  # noqa: F401 — register models

    safe_target = get_safe_db_url()
    logger.info(f"Initializing database: {safe_target}")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified.")
            _seed_default_users()
            _seed_default_warehouse()
            return
        except Exception as exc:
            last_error = exc
            safe_error = re.sub(r"PWD=[^;]+", "PWD=***", str(exc))
            safe_error = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", safe_error)
            logger.warning(
                f"Database init attempt {attempt}/{max_retries} failed: {type(exc).__name__}: {safe_error}"
            )
            if attempt < max_retries:
                time.sleep(retry_delay)

    logger.error("Database initialization could not establish connection after retries.")
    raise last_error


def _seed_default_users():
    """Create default admin and manager users if they do not exist."""
    from app.models.user import User
    from app.core.security import hash_password

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == "admin").first() is None:
            admin = User(
                username="admin",
                email="admin@warehouse.local",
                hashed_password=hash_password("Admin@123"),
                full_name="System Administrator",
                role="ADMIN",
                is_active=True,
            )
            db.add(admin)
            logger.info("Default admin user created.")

        if db.query(User).filter(User.username == "manager").first() is None:
            manager = User(
                username="manager",
                email="manager@warehouse.local",
                hashed_password=hash_password("Manager@123"),
                full_name="Warehouse Manager",
                role="WAREHOUSE_MANAGER",
                is_active=True,
            )
            db.add(manager)
            logger.info("Default manager user created.")

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"User seeding failed: {type(exc).__name__}")
    finally:
        db.close()


def _seed_default_warehouse():
    """Create default warehouse WH-001 if it does not exist (needed for clean production DBs)."""
    from app.models.warehouse import Warehouse

    db = SessionLocal()
    try:
        if db.query(Warehouse).filter(Warehouse.warehouse_id == "WH-001").first() is None:
            wh = Warehouse(
                warehouse_id="WH-001",
                name="Main Distribution Center",
                location="Central India Logistics Hub",
            )
            db.add(wh)
            db.commit()
            logger.info("Default warehouse WH-001 created.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Warehouse seeding failed: {type(exc).__name__}")
    finally:
        db.close()

