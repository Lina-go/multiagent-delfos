"""
API Router - FastAPI routes for the multi-agent system.
"""

import logging
from typing import Optional

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
        tables = []
        if result.get("data"):
            tables = [t.strip() for t in result["data"].split("\n") if t.strip()]
        return {"tables": tables}

    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a table."""
    try:
        result = await run_workflow("Get schema for table {}".format(table_name))
        return {"table": table_name, "schema": result.get("data", "")}

    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))