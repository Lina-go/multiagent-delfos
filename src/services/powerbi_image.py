"""
Service for retrieving Power BI graph images using run_id and tipo_grafico.
Uses Power BI REST API to export report pages as images.
"""
import logging
import base64
from typing import Optional
from urllib.parse import quote

try:
    import aiohttp
except ImportError:
    aiohttp = None

from azure.identity.aio import DefaultAzureCredential
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Power BI API endpoint
POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Map tipo_grafico to Power BI page names (matching MCP server mapping)
VISUAL_PAGE_MAP = {
    "pie": "PieChart",
    "bar": "Bar",
    "line": "Line",
    "stackedbar": "StackedBar",
}


async def get_powerbi_access_token() -> str:
    """
    Get Power BI access token using Azure AD.
    
    Returns:
        str: Access token for Power BI API
    """
    credential = DefaultAzureCredential()
    try:
        token = await credential.get_token(POWER_BI_SCOPE)
        return token.token
    finally:
        await credential.close()


async def list_powerbi_pages(
    workspace_id: str,
    report_id: str,
    access_token: str
) -> Optional[dict]:
    """
    List all pages in a Power BI report.
    
    Args:
        workspace_id: Power BI workspace ID
        report_id: Power BI report ID
        access_token: Power BI API access token
        
    Returns:
        dict: Dictionary mapping displayName -> name (ID), or None if error
    """
    if aiohttp is None:
        return None
    
    pages_url = (
        f"{POWER_BI_API_BASE}/groups/{workspace_id}/"
        f"reports/{report_id}/pages"
    )
    
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(pages_url, headers=headers) as response:
                if response.status == 404:
                    logger.warning(f"Report {report_id} not found")
                    return None
                
                response.raise_for_status()
                result = await response.json()
                
                # Power BI API returns pages in a "value" array
                # Each page has: name (ID), displayName (user-friendly name)
                if "value" in result:
                    page_map = {}
                    page_list = []
                    for page in result["value"]:
                        page_id = page.get("name")  # The ID used in API calls
                        display_name = page.get("displayName", page_id)  # User-friendly name
                        page_map[display_name] = page_id
                        page_list.append(f"{display_name} ({page_id})")
                    
                    logger.info(f"Found {len(page_map)} pages in report: {page_list}")
                    logger.debug(f"Page mapping: {page_map}")
                    return page_map
                else:
                    logger.warning(f"Unexpected response format: {list(result.keys())}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error listing Power BI pages: {e}")
        return None


async def export_powerbi_page(
    workspace_id: str,
    report_id: str,
    page_name: str,
    access_token: str,
    run_id: str
) -> Optional[bytes]:
    """
    Export a Power BI report page as PNG image.
    
    Args:
        workspace_id: Power BI workspace ID
        report_id: Power BI report ID
        page_name: Name of the page to export
        access_token: Power BI API access token
        run_id: Run ID to filter the data in Power BI
        
    Returns:
        bytes: PNG image data or None if error
    """
    if aiohttp is None:
        logger.error("aiohttp is not installed")
        return None
    
    # URL encode the page name to handle special characters
    encoded_page_name = quote(page_name, safe='')
    export_url = (
        f"{POWER_BI_API_BASE}/groups/{workspace_id}/"
        f"reports/{report_id}/pages/{encoded_page_name}/ExportTo"
    )
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Export as PNG with filter for run_id
    payload = {
        "format": "PNG",
        "width": 1920,
        "height": 1080,
        "pages": [page_name]
    }
    
    # Add filter for run_id if needed (Power BI filter syntax)
    # The filter will be applied via the URL parameter in the Power BI report
    # Since the report is already filtered by run_id via URL parameter,
    # we just need to export the page
    
    try:
        timeout = aiohttp.ClientTimeout(total=60.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(export_url, json=payload, headers=headers) as response:
                if response.status == 404:
                    logger.warning(f"Page '{page_name}' not found in report {report_id}")
                    return None
                
                if response.status == 403:
                    logger.error("Access denied to Power BI API. Check permissions.")
                    return None
                
                response.raise_for_status()
                
                # Power BI API returns the image in different formats depending on the endpoint
                # Check content-type to determine response format
                content_type = response.headers.get("content-type", "")
                
                if "image" in content_type:
                    # Direct image response
                    image_data = await response.read()
                    logger.info(f"Successfully exported Power BI page '{page_name}' as image")
                    return image_data
                elif "application/json" in content_type:
                    # JSON response with base64 encoded image
                    result = await response.json()
                    
                    # Power BI ExportTo API may return the image in different fields
                    if "image" in result:
                        image_base64 = result["image"]
                        image_data = base64.b64decode(image_base64)
                        return image_data
                    elif "data" in result:
                        image_base64 = result["data"]
                        image_data = base64.b64decode(image_base64)
                        return image_data
                    elif "value" in result:
                        # Some APIs return in a value array
                        if isinstance(result["value"], list) and len(result["value"]) > 0:
                            first_item = result["value"][0]
                            if "image" in first_item:
                                image_base64 = first_item["image"]
                                image_data = base64.b64decode(image_base64)
                                return image_data
                    
                    logger.warning(f"Unexpected JSON response format from Power BI API: {list(result.keys())}")
                    return None
                else:
                    logger.warning(f"Unexpected content-type from Power BI API: {content_type}")
                    return None
                    
    except aiohttp.ClientResponseError as e:
        logger.error(f"Power BI API error: {e.status} - {e.message}")
        if e.status == 404:
            logger.warning(f"Page '{page_name}' not found in report {report_id}")
            # List available pages to help debug
            try:
                available_pages = await list_powerbi_pages(workspace_id, report_id, access_token)
                if available_pages:
                    logger.info(f"Available pages in report: {available_pages}")
            except Exception:
                pass  # Don't fail if listing pages fails
        return None
    except Exception as e:
        logger.error(f"Error exporting Power BI page: {e}", exc_info=True)
        return None


async def get_powerbi_image(run_id: str, tipo_grafico: str) -> Optional[bytes]:
    """
    Retrieve a Power BI graph image using the run_id and tipo_grafico.
    
    Args:
        run_id: The run_id returned by insert_agent_output_batch
        tipo_grafico: Chart type from VizResult ("pie", "bar", "line", "stackedbar")
        
    Returns:
        bytes: Image data (PNG) or None if not available
        
    Raises:
        Exception: If there's an error retrieving the image
    """
    if aiohttp is None:
        logger.error("aiohttp is not installed. Please add it to dependencies.")
        raise ImportError("aiohttp is required for image retrieval")
    
    settings = get_settings()
    
    # Validate required settings
    if not settings.powerbi_workspace_id or not settings.powerbi_report_id:
        logger.error("Power BI workspace_id and report_id must be configured in settings")
        return None
    
    try:
        # Step 1: Get Power BI access token
        logger.debug(f"Getting Power BI access token for run_id: {run_id}")
        access_token = await get_powerbi_access_token()
        
        # Step 2: List available pages in the report
        logger.debug(f"Listing available pages in report {settings.powerbi_report_id}")
        page_map = await list_powerbi_pages(
            workspace_id=settings.powerbi_workspace_id,
            report_id=settings.powerbi_report_id,
            access_token=access_token
        )
        
        if not page_map:
            logger.error(f"Could not list pages from report {settings.powerbi_report_id}")
            return None
        
        # Step 3: Map tipo_grafico to Power BI page ID
        # The ExportTo endpoint requires the page ID (name), not the displayName
        expected_display_name = VISUAL_PAGE_MAP.get(tipo_grafico.lower())
        page_id = None
        page_display_name = None
        
        if expected_display_name:
            # Try exact match first
            if expected_display_name in page_map:
                page_display_name = expected_display_name
                page_id = page_map[expected_display_name]
                logger.info(f"Found exact match: '{page_display_name}' -> ID: '{page_id}'")
            else:
                # Try case-insensitive match
                expected_lower = expected_display_name.lower()
                for display_name, page_id_value in page_map.items():
                    if display_name.lower() == expected_lower:
                        page_display_name = display_name
                        page_id = page_id_value
                        logger.info(f"Found case-insensitive match: '{page_display_name}' -> ID: '{page_id}'")
                        break
                
                # If still not found, try partial match
                if not page_id:
                    tipo_lower = tipo_grafico.lower()
                    for display_name, page_id_value in page_map.items():
                        display_lower = display_name.lower()
                        if tipo_lower in display_lower or display_lower in tipo_lower:
                            page_display_name = display_name
                            page_id = page_id_value
                            logger.info(f"Found partial match: '{page_display_name}' -> ID: '{page_id}' for tipo_grafico '{tipo_grafico}'")
                            break
        
        if not page_id:
            # Fallback: Try using the descriptive name directly (as MCP server does in URLs)
            if expected_display_name:
                logger.warning(
                    f"Could not find matching page by displayName for tipo_grafico '{tipo_grafico}'. "
                    f"Expected displayName: {expected_display_name}. "
                    f"Available pages: {list(page_map.keys())}. "
                    f"Trying to use descriptive name '{expected_display_name}' directly..."
                )
                # Try to find any page that might match
                page_name = expected_display_name
            else:
                logger.error(
                    f"Unknown tipo_grafico: {tipo_grafico}. Valid values: {list(VISUAL_PAGE_MAP.keys())}. "
                    f"Available pages: {list(page_map.keys())}"
                )
                return None
        else:
            # Use the page ID for the API call
            page_name = page_id
            logger.debug(f"Using page ID '{page_name}' (displayName: '{page_display_name}') for export")
        
        # Step 4: Export the page as image
        logger.debug(f"Exporting Power BI page '{page_name}' for run_id: {run_id}")
        image_data = await export_powerbi_page(
            workspace_id=settings.powerbi_workspace_id,
            report_id=settings.powerbi_report_id,
            page_name=page_name,
            access_token=access_token,
            run_id=run_id
        )
        
        if image_data:
            logger.info(f"Successfully generated image for run_id: {run_id}, tipo_grafico: {tipo_grafico}")
            return image_data
        else:
            logger.warning(f"Failed to generate image for run_id: {run_id}, tipo_grafico: {tipo_grafico}")
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error retrieving image for run_id {run_id}: {e}", exc_info=True)
        return None
