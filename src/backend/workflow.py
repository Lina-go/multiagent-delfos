"""
Multi-Agent Workflow using Microsoft Agent Framework.

Sequential flow: SQLAgent -> Validator -> VizAgent (if visualization)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from azure.identity.aio import DefaultAzureCredential
from agent_framework import (
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
    agents_called: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "message": self.message,
            "intent": self.intent,
            "sql": self.sql,
            "data": self.data,
            "visualization_url": self.visualization_url,
            "agents_called": self.agents_called,
        }


class IntentDetector:
    """Detects user intent from message text."""

    VISUALIZATION_KEYWORDS = [
        "grafico", "grafica", "chart", "visualiz", "barras", "bar",
        "pie", "pastel", "linea", "line", "dona", "donut", "plot",
    ]

    @classmethod
    def detect(cls, message: str) -> str:
        """Detect intent from message."""
        text = message.lower()
        for keyword in cls.VISUALIZATION_KEYWORDS:
            if keyword in text:
                return "visualization"
        return "data_query"


class ResponseParser:
    """Parses agent JSON responses."""

    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from text."""
        if not text:
            return None

        # Try ```json ... ```
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try ``` ... ``` (generic code block)
        match = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try raw JSON object
        match = re.search(r"(\{[^{}]*\"[^{}]*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def extract_sql(text: str) -> Optional[str]:
        """Extract SQL query from text or JSON."""
        if not text:
            return None

        # Try to get from JSON first
        json_data = ResponseParser.extract_json(text)
        if json_data and "sql_query" in json_data:
            return json_data["sql_query"]

        # Fallback: Try ```sql ... ```
        match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback: Try raw SELECT
        match = re.search(r"(SELECT\s+.+?(?:;|$))", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        """Extract Power BI URL from text or JSON."""
        if not text:
            return None

        # Try to get from JSON first
        json_data = ResponseParser.extract_json(text)
        if json_data and "powerbi_url" in json_data:
            return json_data["powerbi_url"]

        # Fallback: regex for Power BI URL
        match = re.search(r"(https?://app\.powerbi\.com[^\s<>\"')\]]+)", text)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def extract_validation(text: str) -> Optional[Dict[str, Any]]:
        """Extract validation result from Validator response."""
        if not text:
            return None

        json_data = ResponseParser.extract_json(text)
        if json_data and "is_valid" in json_data:
            return json_data

        return None

    @staticmethod
    def extract_results(text: str) -> Optional[str]:
        """Extract query results from SQLAgent response as string."""
        if not text:
            return None

        json_data = ResponseParser.extract_json(text)
        if json_data and "results" in json_data:
            results = json_data["results"]
            # Always return as string
            if isinstance(results, str):
                return results
            return json.dumps(results, indent=2, ensure_ascii=False)

        return None

    @staticmethod
    def to_string(value: Any) -> str:
        """Convert any value to string."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, indent=2, ensure_ascii=False)


def parse_conversation(messages: list, result: WorkflowResult) -> None:
    """Parse conversation messages to extract SQL, data, and URLs."""
    for msg in messages:
        if not hasattr(msg, "text") or not msg.text:
            continue

        text = msg.text
        author = getattr(msg, "author_name", "") or ""

        # Track agents
        if author and author not in result.agents_called:
            result.agents_called.append(author)

        # SQLAgent response
        if "SQLAgent" in author:
            if not result.sql:
                result.sql = ResponseParser.extract_sql(text)
            results = ResponseParser.extract_results(text)
            if results:
                result.data = results

        # Validator response
        if "Validator" in author:
            validation = ResponseParser.extract_validation(text)
            if validation and not validation.get("is_valid", True):
                result.errors.extend(validation.get("security_issues", []))
                result.errors.extend(validation.get("schema_issues", []))

        # VizAgent response
        if "VizAgent" in author:
            url = ResponseParser.extract_url(text)
            if url:
                result.visualization_url = url

    # Last message as final response
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "text") and last_msg.text:
            json_data = ResponseParser.extract_json(last_msg.text)
            if json_data:
                if "powerbi_url" in json_data:
                    result.message = f"Visualization ready: {json_data['powerbi_url']}"
                elif "results" in json_data:
                    explanation = json_data.get("explanation", "")
                    results = json_data["results"]
                    results_str = ResponseParser.to_string(results)
                    result.message = f"{explanation}\n\n{results_str}" if explanation else results_str
                else:
                    result.message = last_msg.text
            else:
                result.message = last_msg.text

    # Ensure message and data are strings
    result.message = ResponseParser.to_string(result.message) if result.message else ""
    result.data = ResponseParser.to_string(result.data) if result.data else None


async def run_workflow(message: str, user_id: str = "anonymous") -> dict:
    """
    Execute the multi-agent workflow.

    Args:
        message: User question
        user_id: User identifier

    Returns:
        Dictionary with workflow results
    """
    settings = get_settings()
    result = WorkflowResult()

    logger.info("Starting workflow: %s", message[:100])

    # Detect intent
    result.intent = IntentDetector.detect(message)
    logger.info("Intent: %s", result.intent)

    credential = DefaultAzureCredential()

    try:
        # Connect to MCP server
        async with MCPStreamableHTTPTool(
            name="delfos-mcp",
            url=settings.mcp_server_url,
            timeout=settings.mcp_timeout,
            sse_read_timeout=settings.mcp_sse_timeout,
        ) as mcp:
            logger.info("MCP connected: %s", settings.mcp_server_url)

            # Connect to Azure AI Foundry
            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=credential,
            ) as client:
                logger.info("Azure AI connected")

                # Create agents
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

                # Add VizAgent for visualizations
                if result.intent == "visualization":
                    viz_agent = client.create_agent(
                        name="VizAgent",
                        instructions=AgentPrompts.VISUALIZATION,
                        tools=mcp,
                    )
                    participants.append(viz_agent)

                # Build sequential workflow
                workflow = SequentialBuilder().participants(participants).build()
                logger.info("Running workflow with %d agents", len(participants))

                # Process events
                final_messages = []
                streaming_text = ""

                async for event in workflow.run_stream(message):
                    if isinstance(event, AgentRunUpdateEvent):
                        data = str(getattr(event, "data", ""))
                        streaming_text += data

                    elif isinstance(event, WorkflowOutputEvent):
                        final_messages = event.data
                        logger.info("Workflow completed")

                # Try to extract SQL from streaming text
                if streaming_text and not result.sql:
                    result.sql = ResponseParser.extract_sql(streaming_text)

                # Parse final messages
                if final_messages:
                    parse_conversation(final_messages, result)
                    result.success = True
                    logger.info("Agents called: %s", result.agents_called)
                    logger.info("SQL: %s", result.sql[:50] if result.sql else "None")
                else:
                    result.message = "No response from workflow"
                    logger.warning("No output received")

    except Exception as e:
        logger.error("Workflow error: %s", e, exc_info=True)
        result.success = False
        result.message = f"Error: {e}"
        result.errors.append(str(e))

    finally:
        await credential.close()

    # Fallback message
    if not result.message and result.data:
        result.message = result.data

    return result.to_dict()