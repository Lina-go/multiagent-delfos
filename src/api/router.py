"""
API Router - FastAPI routes.
"""
import logging
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import Response as FastAPIResponse
from src.workflow import run_workflow
from src.models import ChatRequest, ChatResponse
from src.services.chart_image import get_chart_image

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
    tipo_grafico: str = Query(..., description="Chart type from VizResult: 'pie', 'bar', 'line', or 'stackedbar'"),
    data: Optional[str] = Query(None, description="Optional JSON string of data points array")
) -> Response:
    """
    Retrieve a graph image for a given run_id.
    
    Args:
        run_id: The run_id from the visualization result
        tipo_grafico: Chart type from VizResult ("pie", "bar", "line", "stackedbar")
                      This should match the value from response.viz_data.tipo_grafico
        data: Optional JSON string of data points array. If provided, will be passed to chart server.
        
    Returns:
        Response: Image data (PNG) with appropriate content-type
        
    Raises:
        HTTPException: 404 if image not found, 500 if error retrieving
    """
    try:
        data_points = None
        if data:
            try:
                data_points = json.loads(data)
                if not isinstance(data_points, list):
                    logger.warning(f"Data parameter is not a list, ignoring: {type(data_points)}")
                    data_points = None
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse data parameter as JSON: {e}")
                data_points = None
        
        image_data = await get_chart_image(run_id, tipo_grafico, data_points)
        
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

