"""
src/backend/api/router.py
API Router - FastAPI routes.
"""
import logging
from fastapi import APIRouter, HTTPException
from src.backend.workflow import run_workflow
from src.backend.schemas import ChatRequest, ChatResponse

router = APIRouter()
logger = logging.getLogger(__name__)

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
    logger.info(f"Chat request: {request.message[:50]}")
    try:
        result_dict = await run_workflow(
            message=request.message,
            user_id=request.user_id,
        )
        return ChatResponse(**result_dict)
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))