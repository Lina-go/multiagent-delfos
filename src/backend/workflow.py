"""
src/backend/workflow.py
Orquestador del flujo de trabajo multi-agente con lógica condicional.
"""
import logging
import json
import re
from typing import Dict, Any

from azure.identity.aio import DefaultAzureCredential
from agent_framework import (
    MCPStreamableHTTPTool,
    SequentialBuilder,
    WorkflowOutputEvent,
)
from agent_framework_azure_ai import AzureAIAgentClient

from src.backend.config.settings import get_settings
from src.backend.config.prompts import AgentPrompts
from src.backend.schemas import ChatResponse, SQLResult, VizResult

logger = logging.getLogger(__name__)

class JSONParser:
    """Ayuda a extraer JSON limpio de las respuestas del LLM."""
    
    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """Intenta extraer un bloque JSON del texto."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            return {}

async def run_single_agent(agent: Any, input_text: str) -> str:
    """
    Ejecuta un agente de forma aislada usando SequentialBuilder.
    """
    workflow = SequentialBuilder().participants([agent]).build()
    final_text = ""
    async for event in workflow.run_stream(input_text):
        if isinstance(event, WorkflowOutputEvent):
            for msg in event.data:
                if hasattr(msg, "text") and msg.text:
                    final_text = msg.text
    return final_text

async def run_workflow(message: str, user_id: str = "anonymous") -> Dict[str, Any]:
    """
    Ejecuta el flujo: Intent -> SQL -> (Opcional) Viz.
    """
    settings = get_settings()
    response = ChatResponse(success=False, message="Iniciando...", errors=[])
    
    credential = DefaultAzureCredential()

    try:
        async with MCPStreamableHTTPTool(
            name="delfos-mcp",
            url=settings.mcp_server_url,
            timeout=settings.mcp_timeout,
            sse_read_timeout=settings.mcp_sse_timeout,
        ) as mcp:
            
            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=credential,
            ) as client:
                
                # ---------------------------------------------------------
                # PASO 1: DETECCIÓN DE INTENCIÓN
                # ---------------------------------------------------------
                intent_agent = client.create_agent(
                    name="IntentAgent",
                    instructions=AgentPrompts.INTENT_AGENT,
                )
                
                logger.info("Ejecutando IntentAgent...")
                raw_intent = await run_single_agent(intent_agent, message)
                intent_data = JSONParser.extract_json(raw_intent)
                
                intent = intent_data.get("intent", "nivel_puntual")
                response.intent = intent
                logger.info(f"Intent detectado: {intent}")

                # ---------------------------------------------------------
                # PASO 2: GENERACIÓN SQL 
                # ---------------------------------------------------------
                sql_agent = client.create_agent(
                    name="SQLAgent",
                    instructions=AgentPrompts.SQL_AGENT,
                    tools=mcp,
                )
                
                logger.info("Ejecutando SQLAgent...")
                # Usamos el mensaje original del usuario
                raw_sql_result = await run_single_agent(sql_agent, message)
                sql_json = JSONParser.extract_json(raw_sql_result)
                
                if sql_json and "resultados" in sql_json:
                    response.sql_data = SQLResult(**sql_json)
                    response.message = response.sql_data.resumen
                else:
                    response.message = raw_sql_result
                    response.success = True 
                    return response.model_dump()

                # ---------------------------------------------------------
                # PASO 3: VISUALIZACIÓN (VIZ AGENT - Condicional)
                # ---------------------------------------------------------
                if intent == "requiere_visualizacion" and response.sql_data:
                    logger.info("Iniciando VizAgent (Condición cumplida)...")
                    
                    viz_agent = client.create_agent(
                        name="VizAgent",
                        instructions=AgentPrompts.VIZ_AGENT,
                        tools=mcp, 
                    )

                    viz_input = json.dumps(sql_json, indent=2, ensure_ascii=False)
                    raw_viz_result = await run_single_agent(viz_agent, viz_input)
                    viz_json = JSONParser.extract_json(raw_viz_result)
                    
                    if viz_json and "powerbi_url" in viz_json:
                        response.viz_data = VizResult(**viz_json)
                        response.message += f"\nVisualización generada: {response.viz_data.powerbi_url}"
                    else:
                        logger.warning("VizAgent no devolvió una URL válida.")

                response.success = True

    except Exception as e:
        logger.error(f"Error en workflow: {e}", exc_info=True)
        response.success = False
        response.message = f"Error del sistema: {str(e)}"
        response.errors.append(str(e))

    finally:
        await credential.close()

    return response.model_dump()