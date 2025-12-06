"""
API Router - FastAPI routes.
"""
import logging
from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import Response as FastAPIResponse
from src.workflow import run_workflow
from src.models import ChatRequest, ChatResponse
from src.services.powerbi_image import get_powerbi_image

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

@router.get("/graph/{run_id}")
async def get_graph(
    run_id: str,
    tipo_grafico: str = Query(..., description="Chart type from VizResult: 'pie', 'bar', 'line', or 'stackedbar'")
) -> Response:
    """
    Retrieve a graph image for a given run_id.
    
    Args:
        run_id: The run_id from the visualization result
        tipo_grafico: Chart type from VizResult ("pie", "bar", "line", "stackedbar")
                      This should match the value from response.viz_data.tipo_grafico
        
    Returns:
        Response: Image data (PNG) with appropriate content-type
        
    Raises:
        HTTPException: 404 if image not found, 500 if error retrieving
    """
    try:
        image_data = await get_powerbi_image(run_id, tipo_grafico)
        
        if image_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for run_id: {run_id} with tipo_grafico: {tipo_grafico}"
            )
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=graph_{run_id}.png"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving graph image for run_id {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving image: {str(e)}")

