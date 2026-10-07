"""
main.py — FastAPI application entry point.
Sets up CORS, mounts static frontend, registers all API routers,
and initializes the database on startup.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.logger import logger
from app.models.database import init_db
from app.api import auth, warehouses, datasets, analysis, reports, monitoring

settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB. Shutdown: cleanup."""
    logger.info(f"Starting {settings.app_name} [{settings.app_env}]")
    init_db()
    logger.info("Database initialized.")
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

# ── Request logging middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and their response status."""
    logger.info(f"--> {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"<-- {response.status_code} {request.url.path}")
        return response
    except Exception as exc:
        logger.error(f"Unhandled exception for {request.url.path}: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
