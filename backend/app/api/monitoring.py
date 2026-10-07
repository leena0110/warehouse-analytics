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
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.app_name,
        "env": settings.app_env,
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
