"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.
Supports SQLite (local dev) and Azure SQL (production).
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.core.logger import logger

settings = get_settings()

# ── Engine configuration ──────────────────────────────────────────────────────
connect_args = {}
if settings.database_url.startswith("sqlite"):
    # SQLite requires check_same_thread=False for FastAPI's async context
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,          # SQL logging in debug mode
    pool_pre_ping=True,           # Detect stale connections
    pool_recycle=3600,            # Recycle connections every hour
)

# Enable WAL mode for SQLite (better concurrency)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Create all tables and seed initial data."""
    from app.models import user, warehouse, slot, dataset, analysis  # noqa: F401 — register models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")
    _seed_default_users()


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
            logger.info("Default admin user created. Change password in production!")

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
            logger.info("Default manager user created. Change password in production!")

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Seeding failed: {exc}")
    finally:
        db.close()
