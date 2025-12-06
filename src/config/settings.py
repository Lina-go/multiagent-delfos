"""
Application settings using Pydantic BaseSettings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Delfos Multi-Agent System"
    debug: bool = False

    # Azure AI Foundry
    azure_ai_project_endpoint: str = ""
    azure_ai_model_deployment_name: str = "gpt-4o"  # Legacy, kept for compatibility
    
    # Per-agent model configurations (required in .env)
    intent_agent_model: str
    sql_agent_model: str
    viz_agent_model: str
    format_agent_model: str
    graph_executor_model: str = "gpt-4o-mini"

    # MCP Server
    mcp_server_url: str = "https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp"
    mcp_timeout: int = 45  # Reduced from 60 for faster failure detection
    mcp_sse_timeout: int = 30  # Reduced from 45 for faster failure detection
    
    # MCP Chart Server
    mcp_chart_server_url: str = "https://mcp-chart-server.calmocean-fbbefe3a.westus2.azurecontainerapps.io/mcp"

    log_level: str = "DEBUG"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

