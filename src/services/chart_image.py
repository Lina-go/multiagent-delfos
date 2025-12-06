"""
Service for retrieving chart images using MCP chart server.
Uses the MCP chart server API to generate chart images based on run_id and chart type.
"""
import logging
import base64
from typing import Optional, List, Dict, Any

try:
    import aiohttp
except ImportError:
    aiohttp = None

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Map tipo_grafico to chart type names for MCP chart server
CHART_TYPE_MAP = {
    "pie": "pie",
    "bar": "bar",
    "line": "line",
    "stackedbar": "stackedbar",
}


async def get_chart_image(
    run_id: str, 
    tipo_grafico: str, 
    data_points: Optional[List[Dict[str, Any]]] = None
) -> Optional[bytes]:
    """
    Retrieve a chart image using the MCP chart server.
    
    Args:
        run_id: The run_id returned by insert_agent_output_batch
        tipo_grafico: Chart type from VizResult ("pie", "bar", "line", "stackedbar")
        data_points: Optional list of data points to include in the chart.
                     Each point should have x_value, y_value, and category.
        
    Returns:
        bytes: Image data (PNG) or None if not available
    """
    if aiohttp is None:
        logger.error("aiohttp is not installed. Please add it to dependencies.")
        raise ImportError("aiohttp is required for image retrieval")
    
    settings = get_settings()
    
    if not settings.mcp_chart_server_url:
        logger.error("MCP chart server URL must be configured in settings")
        return None
    
    # Map tipo_grafico to chart type
    chart_type = CHART_TYPE_MAP.get(tipo_grafico.lower())
    if not chart_type:
        logger.error(f"Unsupported chart type: {tipo_grafico}")
        return None
    
    try:
        # Try different possible endpoint patterns for MCP chart server
        # Pattern 1: Direct REST API endpoint
        endpoints_to_try = [
            f"{settings.mcp_chart_server_url}/generate",
            f"{settings.mcp_chart_server_url}/chart",
            f"{settings.mcp_chart_server_url}/api/chart",
            f"{settings.mcp_chart_server_url}/mcp/chart",
        ]
        
        # Prepare the request payload
        # The exact structure may vary based on the MCP chart server API
        payload = {
            "run_id": run_id,
            "chart_type": chart_type,
            "format": "png"
        }
        
        # Add data points if provided
        if data_points:
            payload["data"] = data_points
            logger.debug(f"Including {len(data_points)} data points in chart request")
        
        logger.info(f"Requesting chart from MCP chart server: run_id={run_id}, chart_type={chart_type}")
        
        timeout = aiohttp.ClientTimeout(total=60.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            last_error = None
            for chart_url in endpoints_to_try:
                try:
                    async with session.post(chart_url, json=payload) as response:
                        if response.status == 200:
                            content_type = response.headers.get("content-type", "")
                            logger.debug(f"Chart response content-type: {content_type}")
                            
                            # Check if response is an image
                            if "image" in content_type:
                                image_data = await response.read()
                                logger.info(f"Successfully generated chart image from {chart_url}: {len(image_data)} bytes")
                                return image_data
                            else:
                                # Try to parse as JSON in case of error message
                                try:
                                    error_data = await response.json()
                                    logger.warning(f"Chart server at {chart_url} returned JSON instead of image: {error_data}")
                                    # Continue to next endpoint
                                except:
                                    response_text = await response.text()
                                    logger.warning(f"Chart server at {chart_url} returned non-image response: {response_text[:200]}")
                                    # Continue to next endpoint
                        elif response.status == 404:
                            logger.debug(f"Endpoint {chart_url} returned 404, trying next...")
                            # Continue to next endpoint
                        else:
                            response_text = await response.text()
                            logger.debug(f"Endpoint {chart_url} returned status {response.status}: {response_text[:200]}")
                            last_error = f"Status {response.status}: {response_text[:200]}"
                            # Continue to next endpoint
                except aiohttp.ClientError as e:
                    logger.debug(f"Error trying endpoint {chart_url}: {e}")
                    last_error = str(e)
                    # Continue to next endpoint
                    continue
            
            # If we get here, all endpoints failed
            logger.error(f"All chart server endpoints failed. Last error: {last_error}")
            return None
                    
    except Exception as e:
        logger.error(f"Unexpected error retrieving chart image for run_id {run_id}: {e}", exc_info=True)
        return None


async def get_chart_image_base64(
    run_id: str, 
    tipo_grafico: str, 
    data_points: Optional[List[Dict[str, Any]]] = None
) -> Optional[str]:
    """
    Retrieve a chart image as base64 string using the MCP chart server.
    
    Args:
        run_id: The run_id returned by insert_agent_output_batch
        tipo_grafico: Chart type from VizResult ("pie", "bar", "line", "stackedbar")
        data_points: Optional list of data points to include in the chart.
                     Each point should have x_value, y_value, and category.
        
    Returns:
        str: Base64 encoded image data (PNG) or None if not available
    """
    image_data = await get_chart_image(run_id, tipo_grafico, data_points)
    if image_data:
        # Encode to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"Converted chart image to base64: {len(image_base64)} characters")
        return image_base64
    return None


async def download_image_from_url(url: str) -> Optional[bytes]:
    """
    Download an image from a URL and return it as bytes.
    
    Args:
        url: HTTPS URL to the image
        
    Returns:
        bytes: Image data or None if download fails
    """
    if aiohttp is None:
        logger.error("aiohttp is not installed. Please add it to dependencies.")
        raise ImportError("aiohttp is required for downloading images")
    
    if not url or not url.startswith("http"):
        logger.error(f"Invalid URL provided: {url}")
        return None
    
    try:
        timeout = aiohttp.ClientTimeout(total=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        image_data = await response.read()
                        logger.info(f"Successfully downloaded image from URL: {len(image_data)} bytes")
                        return image_data
                    else:
                        logger.warning(f"URL did not return an image. Content-Type: {content_type}")
                        return None
                else:
                    logger.error(f"Failed to download image. Status: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error downloading image from URL {url}: {e}", exc_info=True)
        return None


async def url_to_base64(url: str) -> Optional[str]:
    """
    Download an image from a URL and convert it to base64 string.
    
    Args:
        url: HTTPS URL to the image
        
    Returns:
        str: Base64 encoded image data or None if download/conversion fails
    """
    image_data = await download_image_from_url(url)
    if image_data:
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"Converted image URL to base64: {len(image_base64)} characters")
        return image_base64
    return None

