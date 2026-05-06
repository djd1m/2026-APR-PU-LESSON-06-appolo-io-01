"""SalesRadar — B2B Sales Intelligence API (Apollo.io RF-clone)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from models.database import engine, create_tables
from routers import (
    auth_router, companies_router, contacts_router, sequences_router,
    enrollments_router, activities_router, intents_router,
    analytics_router, billing_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    if settings.DEBUG:
        await create_tables()
        logger.info("Database tables created (DEBUG mode)")
    yield
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="B2B Sales Intelligence Platform — companies, contacts, sequences, scoring, intent signals",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
app.include_router(auth_router, prefix=API)
app.include_router(companies_router, prefix=API)
app.include_router(contacts_router, prefix=API)
app.include_router(sequences_router, prefix=API)
app.include_router(enrollments_router, prefix=API)
app.include_router(activities_router, prefix=API)
app.include_router(intents_router, prefix=API)
app.include_router(analytics_router, prefix=API)
app.include_router(billing_router, prefix=API)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
