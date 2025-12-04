"""
Agent executor for running agents in isolation.
"""
import logging
from typing import Any

from agent_framework import SequentialBuilder, WorkflowOutputEvent

logger = logging.getLogger(__name__)


async def run_single_agent(agent: Any, input_text: str) -> str:
    """
    Execute an agent in isolation using SequentialBuilder.
    """
    workflow = SequentialBuilder().participants([agent]).build()
    all_texts = []
    async for event in workflow.run_stream(input_text):
        if isinstance(event, WorkflowOutputEvent):
            for msg in event.data:
                if hasattr(msg, "text") and msg.text:
                    logger.debug(f"Agent message received: {msg.text[:200]}...")
                    all_texts.append(msg.text)
    logger.debug(f"Total messages received: {len(all_texts)}")
    return all_texts[-1] if all_texts else ""

