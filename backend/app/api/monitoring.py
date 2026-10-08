"""
monitoring.py — Health check and monitoring/metrics API.
"""

import platform
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_db, require_manager_or_admin
from app.core.config import get_settings
from app.models.user import User
from app.models.dataset import Dataset, AnalysisRun
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])
settings = get_settings()

# Track server start time for uptime calculation
_START_TIME = time.time()


@router.get("/health")
def health_check():
    """Basic health check — no auth required."""
    db_type = "azure_sql" if ("mssql" in str(settings.database_url) or settings.sql_server) else "sqlite_local"
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.app_name,
        "env": settings.app_env,
        "database_type": db_type,
    }


@router.get("/db-diagnostic")
def db_diagnostic():
    """
    Safe database and network diagnostic endpoint — no secrets exposed.
    Tests TCP connectivity to port 1433 and reports connection status.
    """
    import socket
    from app.models.database import get_safe_db_url, is_mssql

    target_host = settings.sql_server
    if not target_host and "mssql" in str(settings.database_url):
        try:
            proto, rest = str(settings.database_url).split("://", 1)
            endpoint = rest.rsplit("@", 1)[-1].split("/", 1)[0].split("?")[0]
            target_host = endpoint.split(":")[0]
        except Exception:
            target_host = "warehouseanalytics-sql.database.windows.net"

    tcp_reachable = None
    tcp_latency_ms = None
    tcp_error = None

    if is_mssql and target_host:
        try:
            t0 = time.time()
            s = socket.create_connection((target_host, settings.sql_port or 1433), timeout=5.0)
            tcp_latency_ms = round((time.time() - t0) * 1000, 2)
            s.close()
            tcp_reachable = True
        except Exception as exc:
            tcp_reachable = False
            tcp_error = f"{type(exc).__name__}: {str(exc)}"

    return {
        "database_configured": "azure_sql" if is_mssql else "sqlite_local",
        "safe_target": get_safe_db_url(),
        "network_test": {
            "target_host": target_host if is_mssql else None,
            "port": (settings.sql_port or 1433) if is_mssql else None,
            "tcp_reachable": tcp_reachable,
            "latency_ms": tcp_latency_ms,
            "error": tcp_error,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Application metrics — authenticated users only."""
    uptime_seconds = int(time.time() - _START_TIME)

    total_warehouses = db.query(Warehouse).count()
    total_datasets = db.query(Dataset).count()
    processed_datasets = db.query(Dataset).filter(Dataset.status == "PROCESSED").count()
    failed_datasets = db.query(Dataset).filter(Dataset.status == "FAILED").count()
    total_analysis_runs = db.query(AnalysisRun).count()
    latest_run = db.query(AnalysisRun).order_by(AnalysisRun.run_at.desc()).first()

    # System metrics via psutil (optional dependency)
    cpu_percent = None
    memory_percent = None
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
    except ImportError:
        pass

    return {
        "uptime_seconds": uptime_seconds,
        "process_uptime_seconds": uptime_seconds,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "environment": settings.app_env,
        "azure_storage_active": settings.is_azure_storage_enabled,
        "appinsights_active": settings.is_appinsights_enabled,
        "database_type": "azure_sql" if "mssql" in settings.database_url else "sqlite_local",
        "counts": {
            "warehouses": total_warehouses,
            "datasets": total_datasets,
            "datasets_processed": processed_datasets,
            "datasets_failed": failed_datasets,
            "analysis_runs": total_analysis_runs,
        },
        "latest_analysis": {
            "run_at": latest_run.run_at.isoformat() if latest_run else None,
            "utilization_pct": latest_run.utilization_pct if latest_run else None,
            "risk_level": latest_run.risk_level if latest_run else None,
        } if latest_run else None,
        "server": {
            "python": platform.python_version(),
            "os": platform.system(),
        },
    }
