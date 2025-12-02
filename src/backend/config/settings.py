"""
Application settings using Pydantic BaseSettings.
All configuration is loaded from environment variables.
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

    # Application
    app_name: str = "Delfos Multi-Agent System"
    debug: bool = False

    # Azure AI Foundry (usa az login para autenticación)
    azure_ai_project_endpoint: str = ""
    azure_ai_model_deployment_name: str = "gpt-4.1-mini"

    # MCP Server - Deployed Azure Functions
    mcp_server_url: str = "https://func-mcp-n2z2m7tmh3kvk.azurewebsites.net/mcp"

    # Power BI (opcional)
    powerbi_workspace_id: Optional[str] = None
    powerbi_report_id: Optional[str] = None

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
