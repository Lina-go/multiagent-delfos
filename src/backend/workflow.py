"""
Multi-Agent Workflow using Microsoft Agent Framework.

Uses SequentialBuilder with Azure AI Foundry agents.
Flow: SQLAgent -> Validator -> VizAgent (if needed)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from azure.identity.aio import DefaultAzureCredential
from agent_framework import (
    ChatMessage,
    MCPStreamableHTTPTool,
    SequentialBuilder,
    WorkflowOutputEvent,
    AgentRunUpdateEvent,
)
from agent_framework_azure_ai import AzureAIAgentClient

from src.backend.config.settings import get_settings
from src.backend.config.prompts import AgentPrompts

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Result of the multi-agent workflow."""

    success: bool = False
    message: str = ""
    intent: str = "data_query"
    sql: Optional[str] = None
    data: Optional[str] = None
    visualization_url: Optional[str] = None
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "message": self.message,
            "intent": self.intent,
            "sql": self.sql,
            "data": self.data,
            "visualization_url": self.visualization_url,
        }


class IntentDetector:
    """Detects user intent from message text."""

    VISUALIZATION_KEYWORDS = [
        "grafico", "grafica", "chart", "visualiz", "barras", "bar",
        "pie", "pastel", "linea", "line", "dona", "donut", "plot"
    ]

    @classmethod
    def detect(cls, message: str) -> str:
        """Detect intent from message."""
        text = message.lower()
        if any(kw in text for kw in cls.VISUALIZATION_KEYWORDS):
            return "visualization"
        return "data_query"


class ResponseParser:
    """Parses agent responses to extract SQL, URLs, and data."""

    @staticmethod
    def extract_sql(text: str) -> Optional[str]:
        """Extract SQL query from text."""
        if not text:
            return None

        match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match = re.search(r"```\s*(SELECT.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        match = re.search(r"(SELECT\s+.+?;)", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        """Extract URL from text."""
        if not text:
            return None

        match = re.search(r"(https?://app\.powerbi\.com[^\s<>\"')\]]+)", text)
        if match:
            return match.group(1)

        match = re.search(r"(https?://[^\s<>\"')\]]+)", text)
        if match:
            return match.group(1)

        return None


def parse_conversation(messages: list, result: WorkflowResult) -> None:
    """Parse conversation messages to extract SQL, data, and URLs."""
    for msg in messages:
        if not hasattr(msg, "text") or not msg.text:
            continue

        text = msg.text
        author = getattr(msg, "author_name", "") or ""

        if not result.sql:
            result.sql = ResponseParser.extract_sql(text)

        url = ResponseParser.extract_url(text)
        if url and "powerbi" in url.lower():
            result.visualization_url = url

        if "SQLAgent" in author and text:
            result.data = text

    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "text") and last_msg.text:
            result.message = last_msg.text


async def run_workflow(message: str, user_id: str = "anonymous") -> dict:
    """
    Execute the multi-agent workflow using SequentialBuilder.

    Args:
        message: User question in Spanish or English
        user_id: User identifier

    Returns:
        Dictionary with workflow results
    """
    settings = get_settings()
    result = WorkflowResult()

    logger.info("Starting workflow for: %s", message[:100])

    result.intent = IntentDetector.detect(message)
    logger.info("Detected intent: %s", result.intent)

    credential = DefaultAzureCredential()

    try:
        async with MCPStreamableHTTPTool(
            name="delfos-mcp",
            url=settings.mcp_server_url,
            timeout=settings.mcp_timeout,
            sse_read_timeout=settings.mcp_sse_timeout,
        ) as mcp:
            logger.info("MCP connected to: %s", settings.mcp_server_url)

            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=credential,
            ) as client:
                logger.info("Azure AI Foundry connected")

                sql_agent = client.create_agent(
                    name="SQLAgent",
                    instructions=AgentPrompts.SQL_AGENT,
                    tools=mcp,
                )

                validator = client.create_agent(
                    name="Validator",
                    instructions=AgentPrompts.VALIDATOR,
                )

                participants = [sql_agent, validator]

                if result.intent == "visualization":
                    viz_agent = client.create_agent(
                        name="VizAgent",
                        instructions=AgentPrompts.VISUALIZATION,
                        tools=mcp,
                    )
                    participants.append(viz_agent)

                workflow = SequentialBuilder().participants(participants).build()

                logger.info("Running sequential workflow with %d agents", len(participants))

                final_messages = []
                async for event in workflow.run_stream(message):
                    if isinstance(event, AgentRunUpdateEvent):
                        logger.debug("[%s]: %s", event.executor_id, str(event.data)[:100])
                    elif isinstance(event, WorkflowOutputEvent):
                        final_messages = event.data
                        logger.debug("WorkflowOutputEvent received")

                if final_messages:
                    logger.info("Workflow completed with %d messages", len(final_messages))
                    parse_conversation(final_messages, result)
                    result.success = True
                else:
                    result.message = "No response from workflow"
                    logger.warning("No output event received")

    except Exception as e:
        logger.error("Workflow error: %s", e, exc_info=True)
        result.success = False
        result.message = "Error: {}".format(str(e))
        result.errors.append(str(e))

    finally:
        await credential.close()

    if not result.message and result.data:
        result.message = result.data

    return result.to_dict()