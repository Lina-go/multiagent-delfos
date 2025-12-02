"""
API Router - FastAPI routes for the multi-agent system.

Endpoints:
- POST /chat - Process a chat message through multi-agent workflow
- GET /health - Health check
- GET /tables - List database tables
- GET /schema/{table} - Get table schema
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.workflow import run_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic models for FastAPI
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    user_id: Optional[str] = "anonymous"


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    success: bool
    message: str
    intent: Optional[str] = None
    sql: Optional[str] = None
    data: Optional[str] = None
    visualization_url: Optional[str] = None


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "delfos-multi-agent",
        "version": "0.1.0",
        "agents": ["Coordinator", "SQLAgent", "Validator", "VizAgent"],
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message through the multi-agent workflow.

    Flow (all agents use LLM):
    1. Coordinator: Analiza intent y contexto
    2. SQLAgent: Genera SQL y ejecuta via MCP
    3. Validator: Revisa SQL por seguridad
    4. VizAgent: Crea visualización via MCP (si aplica)
    """
    logger.info(f"Chat request: {request.message[:50]}...")

    try:
        result = await run_workflow(
            message=request.message,
            user_id=request.user_id,
        )

        return ChatResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            intent=result.get("intent"),
            sql=result.get("sql"),
            data=result.get("data"),
            visualization_url=result.get("visualization_url"),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def list_tables():
    """List all database tables."""
    try:
        # Use workflow to list tables
        result = await run_workflow("List all tables in the database")
        return {"tables": result.get("data", "").split("\n") if result.get("data") else []}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a table."""
    try:
        result = await run_workflow(f"Get the schema for table {table_name}")
        return {"table": table_name, "schema": result.get("data", "")}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
