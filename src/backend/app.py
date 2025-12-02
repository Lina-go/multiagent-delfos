"""
FastAPI Application - Delfos Multi-Agent System.
"""

import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

for lib in ["httpx", "httpcore", "azure", "urllib3"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.router import router
from src.backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.getLogger("src").setLevel(log_level)

app = FastAPI(
    title="Delfos Multi-Agent System",
    description="Multi-agent system for SQL queries and visualization",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["api"])


@app.get("/")
async def root():
    """Root endpoint with system info."""
    return {
        "name": "Delfos Multi-Agent System",
        "version": "0.1.0",
        "docs": "/docs",
        "mcp_server": settings.mcp_server_url,
        "azure_endpoint": settings.azure_ai_project_endpoint,
        "log_level": settings.log_level,
    }