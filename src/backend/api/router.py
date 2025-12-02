"""
API Router - FastAPI routes for the multi-agent system.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.workflow import run_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


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
    agents_called: Optional[List[str]] = None


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "delfos-multi-agent",
        "version": "0.1.0",
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the multi-agent workflow."""
    logger.info("Chat request: %s", request.message[:50])

    try:
        result = await run_workflow(
            message=request.message,
            user_id=request.user_id,
        )
        return ChatResponse(**result)

    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def list_tables():
    """List all database tables."""
    try:
        result = await run_workflow("List all tables in the database")
        return {"tables": result.get("data", "")}

    except Exception as e:
        logger.error("Tables error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    try:
        result = await run_workflow(f"Get schema for table {table_name}")
        return {"table": table_name, "schema": result.get("data", "")}

    except Exception as e:
        logger.error("Schema error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))