"""
Multi-Agent Workflow - Sistema con GroupChat y Coordinator.

Flujo:
    Usuario → Coordinator (decide quién habla) → Agentes colaboran → Respuesta

Usa GroupChatBuilder con una función selector que decide:
- SQLAgent: para queries SQL
- Validator: para revisar seguridad
- VizAgent: para visualizaciones

Los agentes ven toda la conversación y pueden colaborar.
"""

import logging
from typing import cast

from azure.identity.aio import DefaultAzureCredential
from agent_framework import (
    ChatMessage,
    GroupChatBuilder,
    GroupChatStateSnapshot,
    MCPStreamableHTTPTool,
    Role,
    WorkflowOutputEvent,
    AgentRunUpdateEvent,
)
from agent_framework_azure_ai import AzureAIAgentClient

from src.backend.config.settings import get_settings
from src.backend.config.prompts import AgentPrompts

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def select_next_speaker(state: GroupChatStateSnapshot) -> str | None:
    """
    Función que decide quién habla siguiente.

    Lógica:
    1. SQLAgent primero (genera y ejecuta SQL)
    2. Validator segundo (revisa seguridad)
    3. VizAgent tercero (si se pide visualización)
    4. Terminar
    """
    round_idx = state["round_index"]
    history = state["history"]
    task = state["task"]

    # Obtener el texto de la tarea
    task_text = task.text.lower() if hasattr(task, 'text') and task.text else ""

    # Detectar si pide visualización
    wants_viz = any(kw in task_text for kw in [
        "gráfico", "grafico", "chart", "visualiz", "barras", "pie", "línea", "linea"
    ])

    logger.debug(f"Round {round_idx}, wants_viz={wants_viz}")

    # Obtener último speaker
    last_speaker = history[-1].speaker if history else None
    logger.debug(f"Last speaker: {last_speaker}")

    # Lógica de selección
    if round_idx == 0:
        return "SQLAgent"
    elif round_idx == 1:
        return "Validator"
    elif round_idx == 2 and wants_viz:
        return "VizAgent"
    else:
        return None  # Terminar


async def run_workflow(message: str, user_id: str = "anonymous") -> dict:
    """
    Ejecuta el workflow multi-agente con GroupChat.

    Args:
        message: Pregunta del usuario (español o inglés)
        user_id: Identificador del usuario

    Returns:
        Dict con success, message, sql, data, visualization_url
    """
    settings = get_settings()
    logger.info(f"=== INICIO WORKFLOW ===")
    logger.info(f"Mensaje: {message}")
    logger.info(f"User ID: {user_id}")

    # Crear credenciales Azure (usa az login)
    credential = DefaultAzureCredential()

    try:
        # Conectar al servidor MCP
        logger.info(f"Conectando a MCP: {settings.mcp_server_url}")
        async with MCPStreamableHTTPTool(
            name="delfos-mcp",
            url=settings.mcp_server_url,
        ) as mcp:
            logger.info("MCP conectado OK")

            # Crear cliente Azure AI Foundry
            logger.info(f"Conectando a Foundry: {settings.azure_ai_project_endpoint}")
            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=credential,
            ) as client:
                logger.info("Foundry conectado OK")

                # Crear agentes especialistas
                sql_agent = client.create_agent(
                    name="SQLAgent",
                    description="Genera y ejecuta consultas SQL en FinancialDB",
                    instructions=AgentPrompts.SQL_AGENT,
                    tools=mcp,
                )
                logger.info("SQLAgent creado (con MCP)")

                validator = client.create_agent(
                    name="Validator",
                    description="Revisa consultas SQL por seguridad y corrección",
                    instructions=AgentPrompts.VALIDATOR,
                )
                logger.info("Validator creado")

                viz_agent = client.create_agent(
                    name="VizAgent",
                    description="Crea visualizaciones en Power BI",
                    instructions=AgentPrompts.VISUALIZATION,
                    tools=mcp,
                )
                logger.info("VizAgent creado (con MCP)")

                # Construir GroupChat con función selector
                workflow = (
                    GroupChatBuilder()
                    .select_speakers(select_next_speaker, display_name="Coordinator")
                    .participants([sql_agent, validator, viz_agent])
                    .build()
                )
                logger.info("Workflow GroupChat construido")

                # Ejecutar workflow
                logger.info(f"Ejecutando workflow...")
                final_conversation = []

                async for event in workflow.run_stream(message):
                    # Log de eventos en tiempo real
                    if isinstance(event, AgentRunUpdateEvent):
                        logger.debug(f"[{event.executor_id}]: {event.data}")
                    elif isinstance(event, WorkflowOutputEvent):
                        final_conversation = cast(list[ChatMessage], event.data)
                        logger.info(f"Workflow completado con {len(final_conversation)} mensajes")

                # Parsear resultado
                result = _parse_workflow_result(final_conversation, message)
                logger.info(f"=== FIN WORKFLOW === Success: {result['success']}")
                return result

    except Exception as e:
        logger.error(f"Error en workflow: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "intent": "unknown",
            "sql": None,
            "data": None,
            "visualization_url": None,
        }

    finally:
        await credential.close()


def _parse_workflow_result(conversation: list[ChatMessage], original_message: str) -> dict:
    """
    Parsea el resultado del workflow.
    """
    result = {
        "success": True,
        "message": "",
        "intent": "data_query",
        "sql": None,
        "data": None,
        "visualization_url": None,
    }

    logger.debug(f"Parseando {len(conversation)} mensajes")

    # Detectar intent del mensaje original
    if any(kw in original_message.lower() for kw in ["gráfico", "grafico", "chart", "visualiz"]):
        result["intent"] = "visualization"

    # Recorrer mensajes de los agentes
    for msg in conversation:
        author = msg.author_name or ""
        text = msg.text or ""

        logger.debug(f"Mensaje de [{author}]: {text[:100]}...")

        # Extraer SQL
        sql = _extract_sql(text)
        if sql and not result["sql"]:
            result["sql"] = sql
            logger.debug(f"SQL extraído: {sql[:50]}...")

        # Extraer URL de Power BI
        url = _extract_url(text)
        if url and "powerbi" in url.lower():
            result["visualization_url"] = url
            logger.debug(f"URL Power BI: {url}")

        # Guardar datos del SQLAgent
        if author == "SQLAgent" and text:
            result["data"] = text

    # Usar el último mensaje como respuesta principal
    if conversation:
        last_msg = conversation[-1]
        if last_msg.text:
            result["message"] = last_msg.text

    # Si no hay mensaje, usar data
    if not result["message"] and result["data"]:
        result["message"] = result["data"]

    return result


def _extract_sql(text: str) -> str:
    """Extrae SQL del texto."""
    import re

    # Buscar en bloques de código SQL
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Buscar SELECT ... ;
    match = re.search(r"(SELECT\s+.*?;)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return ""


def _extract_url(text: str) -> str:
    """Extrae URL del texto."""
    import re
    match = re.search(r"https?://[^\s<>\"'\)]+", text)
    return match.group(0) if match else ""
