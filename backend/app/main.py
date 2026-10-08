"""
main.py — FastAPI application entry point.
Sets up CORS, mounts static frontend, registers all API routers,
and initializes the database on startup.

Application Insights integration:
  When AZURE_APPINSIGHTS_CONNECTION_STRING is configured, the log_requests
  middleware creates an opencensus request span per HTTP call, exporting
  method/path/status/duration to the App Insights Requests table.
  Log records are forwarded via AzureLogHandler (app/core/logger.py).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
import app.core.logger as _logger_module          # module import to read live state
from app.core.logger import logger
from app.models.database import init_db
from app.api import auth, warehouses, datasets, analysis, reports, monitoring

settings = get_settings()

# ── Try to import opencensus tracing (optional — only used when App Insights is on)
try:
    from opencensus.trace import tracer as _oc_tracer_mod
    from opencensus.trace.samplers import AlwaysOnSampler as _AlwaysOnSampler
    _OPENCENSUS_AVAILABLE = True
except ImportError:
    _oc_tracer_mod = None          # type: ignore[assignment]
    _AlwaysOnSampler = None        # type: ignore[assignment]
    _OPENCENSUS_AVAILABLE = False


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB. Shutdown: cleanup."""
    logger.info(f"Starting {settings.app_name} [{settings.app_env}]")
    if _logger_module._appinsights_initialized:
        logger.info("Application Insights telemetry is active (logs + request traces).")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(
            f"Database initialization could not complete during startup ({type(exc).__name__}). "
            "Server will remain online; connections will be established upon database availability."
        )
    yield
    logger.info("Application shutting down.")


# ── App instance ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="AI-Based Warehouse Slot Utilization Analyzer — Cloud Computing Project",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Request logging + App Insights telemetry middleware ───────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all incoming requests and their response status.
    When Application Insights is configured, also exports each HTTP request
    as a span to the App Insights Requests table via opencensus AzureExporter.
    Unhandled exceptions are logged with full stack traces (logger.exception)
    so App Insights captures them in the Exceptions table.
    """
    logger.info(f"--> {request.method} {request.url.path}")

    _exporter = _logger_module._azure_exporter
    _use_tracing = _OPENCENSUS_AVAILABLE and _exporter is not None

    if _use_tracing:
        # Create a fresh tracer per request (AzureExporter is shared/thread-safe).
        # Each span maps to one row in App Insights → Requests table.
        span_name = f"{request.method} {request.url.path}"
        req_tracer = _oc_tracer_mod.Tracer(           # type: ignore[union-attr]
            exporter=_exporter,
            sampler=_AlwaysOnSampler(),               # type: ignore[call-arg]
        )
        with req_tracer.span(name=span_name) as span:
            span.add_attribute("http.method", request.method)
            span.add_attribute("http.route", request.url.path)
            span.add_attribute("http.host", request.url.hostname or "")
            try:
                response = await call_next(request)
                span.add_attribute("http.status_code", response.status_code)
                logger.info(f"<-- {response.status_code} {request.url.path}")
                return response
            except Exception as exc:
                span.add_attribute("http.status_code", 500)
                # logger.exception sends full traceback to App Insights Exceptions table
                logger.exception(f"Unhandled exception for {request.url.path}: {exc}")
                return JSONResponse(
                    status_code=500, content={"detail": "Internal server error"}
                )
    else:
        # Plain middleware path — no tracing, still logs exceptions with full trace
        try:
            response = await call_next(request)
            logger.info(f"<-- {response.status_code} {request.url.path}")
            return response
        except Exception as exc:
            logger.exception(f"Unhandled exception for {request.url.path}: {exc}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )


# ── API Routers ───────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(warehouses.router)
app.include_router(datasets.router)
app.include_router(analysis.router)
app.include_router(reports.router)
app.include_router(monitoring.router)

# ── Static Frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve the SPA frontend for all non-API routes."""
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse(status_code=404, content={"detail": "Frontend not built."})


@app.get("/", include_in_schema=False)
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": settings.app_name, "docs": "/api/docs"})
