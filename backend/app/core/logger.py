"""
logger.py — Structured application logging.
Logs to console (dev) and optionally to Azure Application Insights (production).
"""

import logging
import sys
from datetime import datetime
from app.core.config import get_settings

settings = get_settings()

# ── Configure root logger ─────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_LEVEL = logging.DEBUG if settings.debug else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("warehouse_app.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("warehouse_analyzer")

# ── Azure Application Insights (optional) ─────────────────────────────────────
if settings.is_appinsights_enabled:
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        azure_handler = AzureLogHandler(
            connection_string=settings.azure_appinsights_connection_string
        )
        logger.addHandler(azure_handler)
        logger.info("Azure Application Insights logging enabled.")
    except ImportError:
        logger.warning(
            "opencensus-ext-azure not installed — Application Insights logging disabled."
        )
    except Exception as exc:
        logger.warning(f"Application Insights handler error: {exc}")
else:
    logger.info("Application Insights not configured — using local logging only.")


# ── Audit event helpers ───────────────────────────────────────────────────────

def log_event(event: str, user: str = "system", details: str = ""):
    """Log a structured audit event."""
    logger.info(f"EVENT={event} | USER={user} | DETAILS={details}")


def log_error(error: str, user: str = "system", details: str = ""):
    """Log a structured error event."""
    logger.error(f"ERROR={error} | USER={user} | DETAILS={details}")


def log_security(event: str, user: str = "unknown", details: str = ""):
    """Log a security-related event."""
    logger.warning(f"SECURITY={event} | USER={user} | DETAILS={details}")
