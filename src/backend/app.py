"""
FastAPI Application - Delfos Multi-Agent System

Simple multi-agent system for SQL queries and visualization.
Uses MCP to connect to the deployed Azure Functions server.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.router import router
from src.backend.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Delfos Multi-Agent System",
    description="""
Multi-agent system for SQL queries and visualization on FinancialDB.

## Flow
1. User sends natural language question (Spanish or English)
2. SQLAgent generates SQL and executes via MCP
3. VisualizationAgent creates Power BI chart via MCP (if requested)

## MCP Tools Used
- `execute_sql_query` - Run SQL queries
- `list_tables` - Get database tables
- `get_table_schema` - Get table columns
- `insert_agent_output_batch` - Store data for visualization
- `generate_powerbi_url` - Get Power BI URL

## Endpoints
- `POST /api/chat` - Send a chat message
- `GET /api/tables` - List database tables
- `GET /api/schema/{table}` - Get table schema
    """,
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router, prefix="/api", tags=["api"])


@app.get("/")
async def root():
    """Root endpoint."""
    settings = get_settings()
    return {
        "name": "Delfos Multi-Agent System",
        "version": "0.1.0",
        "mcp_server": settings.mcp_server_url,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
