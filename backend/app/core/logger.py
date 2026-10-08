"""
logger.py — Structured application logging with Azure Application Insights.

In LOCAL mode:   logs go to console + file only.
In AZURE mode:   logs forwarded to App Insights via AzureLogHandler (Traces table)
                 and HTTP request spans exported via AzureExporter (Requests table).

Module-level state (set once at startup, never modified afterward):
  _appinsights_initialized — True only when AzureLogHandler was successfully attached.
  _azure_exporter          — AzureExporter instance for request tracing, or None.
"""

import logging
import sys
from typing import Optional
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

# ── Azure Application Insights — actual initialization state ──────────────────
# These are set once at module load time and never changed afterward.
# Other modules must import IS_APPINSIGHTS_ACTIVE / _azure_exporter from here.

_appinsights_initialized: bool = False
_azure_exporter: Optional[object] = None  # opencensus AzureExporter or None


def is_appinsights_active() -> bool:
    """
    Return True only if App Insights was successfully initialized at startup.
    This reflects actual handler attachment, not merely whether the env var is set.
    Use this instead of settings.is_appinsights_enabled for runtime status checks.
    """
    return _appinsights_initialized


if settings.is_appinsights_enabled:
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        from opencensus.ext.azure.trace_exporter import AzureExporter

        # ── Log handler: sends all logger.* calls to App Insights Traces table ──
        _conn_str = settings.azure_appinsights_connection_string
        _azure_log_handler = AzureLogHandler(connection_string=_conn_str)
        # Python 3.13 compatibility: Python 3.13 logging.Handler.handle requires self.lock
        # to be a context manager (threading.RLock). opencensus AzureLogHandler defaults
        # self.lock to None and sets self.lock = None in createLock(). We provide a real RLock.
        import threading
        _azure_log_handler.lock = threading.RLock()
        _azure_log_handler.createLock = lambda: setattr(_azure_log_handler, "lock", threading.RLock())
        logger.addHandler(_azure_log_handler)

        # ── Trace exporter: used by request middleware to send HTTP spans ───────
        # Stored as module-level variable so main.py can import and reuse it
        # without re-reading settings. Creating per-request would be wasteful.
        _azure_exporter = AzureExporter(connection_string=_conn_str)

        _appinsights_initialized = True
        logger.info(
            "Azure Application Insights initialized: "
            "log handler attached, trace exporter ready."
        )

    except ImportError:
        logger.warning(
            "opencensus-ext-azure not installed — "
            "Application Insights telemetry disabled. "
            "Install with: pip install opencensus-ext-azure"
        )
    except Exception as exc:
        if "_azure_log_handler" in locals():
            try:
                logger.removeHandler(_azure_log_handler)
            except Exception:
                pass
        _appinsights_initialized = False
        _azure_exporter = None
        logger.warning(
            f"Application Insights initialization failed ({type(exc).__name__}): {exc}. "
            "Continuing without telemetry."
        )
else:
    logger.info("Application Insights not configured — local logging only.")


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
