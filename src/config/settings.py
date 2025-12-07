"""
Application settings using Pydantic BaseSettings.
"""

from functools import lru_cache
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
    azure_ai_model_deployment_name: str = "gpt-4o"
    
    # Per-agent model configurations
    intent_agent_model: str
    sql_agent_model: str
    viz_agent_model: str
    format_agent_model: str
    graph_executor_model: str
    anthropic_api_key: str

    # MCP Server
    mcp_server_url: str = "https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp"
    mcp_timeout: int = 60
    mcp_sse_timeout: int = 15 
    
    # MCP Chart Server
    mcp_chart_server_url: str = "https://mcp-chart-server.calmocean-fbbefe3a.westus2.azurecontainerapps.io/mcp"

    log_level: str = "INFO"

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

