"""
CRM Intelligence Engine — FastAPI Application.

Serves the complete pipeline as a REST API:
- Profile CRUD (brands + verticals)
- File upload with data scanning
- Report generation with SSE progress streaming
- Reports listing and DOCX download
- Section registry
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import profiles, reports, generate, sections, settings, compare

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    logger.info("CRM Intelligence API starting...")
    yield
    logger.info("CRM Intelligence API shutting down...")


app = FastAPI(
    title="CRM Intelligence Engine",
    description="AI-powered CRM campaign analysis and executive report generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend (dev: localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount routes
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profiles"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(generate.router, prefix="/api/generate", tags=["Generate"])
app.include_router(sections.router, prefix="/api/sections", tags=["Sections"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(compare.router, prefix="/api/compare", tags=["Compare"])


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
