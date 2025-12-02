"""
FastAPI Application - Delfos Multi-Agent System.
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.router import router
from src.backend.config.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
    """Root endpoint."""
    return {
        "name": "Delfos Multi-Agent System",
        "version": "0.1.0",
        "mcp_server": settings.mcp_server_url,
        "azure_endpoint": settings.azure_ai_project_endpoint,
        "log_level": settings.log_level,
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run("src.backend.app:app", host="0.0.0.0", port=8000, reload=True)