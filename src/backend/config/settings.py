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
    azure_ai_model_deployment_name: str = "gpt-4o"

    # MCP Server
    mcp_server_url: str = "https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp"
    mcp_timeout: int = 30
    mcp_sse_timeout: int = 20

    # Power BI
    powerbi_workspace_id: Optional[str] = None
    powerbi_report_id: Optional[str] = None

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()