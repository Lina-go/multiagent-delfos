"""
Multi-agent workflow orchestrator with conditional logic.
"""
import logging
import json
import time
from typing import Dict, Any

from azure.identity.aio import DefaultAzureCredential
from agent_framework import MCPStreamableHTTPTool
from agent_framework_azure_ai import AzureAIAgentClient

from src.config.settings import get_settings
from src.config.prompts import AgentPrompts
from src.models import ChatResponse, SQLResult, VizResult, AgentOutput
from src.services.logger import AgentLogger
from src.agents.executor import run_single_agent
from src.utils.json_parser import JSONParser

logger = logging.getLogger(__name__)


async def run_workflow(message: str, user_id: str = "anonymous") -> Dict[str, Any]:
    """
    Execute the workflow: Intent -> SQL -> (Optional) Viz.
    """
    settings = get_settings()
    response = ChatResponse(success=False, message="Iniciando...", errors=[])

    agent_logger = AgentLogger()
    agent_logger.start_session(user_id=user_id, user_message=message)

    credential = DefaultAzureCredential()

    try:
        async with MCPStreamableHTTPTool(
            name="delfos-mcp",
            url=settings.mcp_server_url,
            timeout=settings.mcp_timeout,
            sse_read_timeout=settings.mcp_sse_timeout,
            approval_mode="never_require",
        ) as mcp:
            
            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.azure_ai_model_deployment_name,
                async_credential=credential,
            ) as client:
                
                # ---------------------------------------------------------
                # STEP 1: INTENT DETECTION
                # ---------------------------------------------------------
                intent_agent = client.create_agent(
                    name="IntentAgent",
                    instructions=AgentPrompts.INTENT_AGENT,
                )
                
                logger.info("Executing IntentAgent...")
                start_time = time.time()
                raw_intent = await run_single_agent(intent_agent, message)
                elapsed_ms = (time.time() - start_time) * 1000
                intent_data = JSONParser.extract_json(raw_intent)

                agent_logger.log_agent_response(
                    agent_name="IntentAgent",
                    raw_response=raw_intent,
                    parsed_response=intent_data,
                    input_text=message,
                    execution_time_ms=elapsed_ms,
                )

                # Add IntentAgent output to response
                response.agent_outputs.append(AgentOutput(
                    agent_name="IntentAgent",
                    raw_response=raw_intent,
                    parsed_response=intent_data,
                    execution_time_ms=elapsed_ms,
                    input_text=message,
                ))

                intent = intent_data.get("intent", "nivel_puntual")
                response.intent = intent
                logger.info(f"Intent detected: {intent}")

                # ---------------------------------------------------------
                # STEP 2: SQL GENERATION
                # ---------------------------------------------------------
                sql_agent = client.create_agent(
                    name="SQLAgent",
                    instructions=AgentPrompts.SQL_AGENT,
                    tools=mcp,
                )
                
                logger.info("Executing SQLAgent...")
                start_time = time.time()
                # Make the SQLAgent input explicit - it should generate and execute SQL, not classify intents
                sql_input = f"Genera y ejecuta una consulta SQL para responder: {message}"
                raw_sql_result = await run_single_agent(sql_agent, sql_input)
                elapsed_ms = (time.time() - start_time) * 1000
                sql_json = JSONParser.extract_json(raw_sql_result)

                agent_logger.log_agent_response(
                    agent_name="SQLAgent",
                    raw_response=raw_sql_result,
                    parsed_response=sql_json,
                    input_text=sql_input,
                    execution_time_ms=elapsed_ms,
                )

                # Add SQLAgent output to response
                response.agent_outputs.append(AgentOutput(
                    agent_name="SQLAgent",
                    raw_response=raw_sql_result,
                    parsed_response=sql_json,
                    execution_time_ms=elapsed_ms,
                    input_text=sql_input,
                ))

                # Check if SQLAgent returned valid JSON with results
                if sql_json and "resultados" in sql_json:
                    try:
                        response.sql_data = SQLResult(**sql_json)
                        response.message = response.sql_data.resumen
                        response.success = True
                    except Exception as e:
                        logger.warning(f"Error parsing SQLResult: {e}")
                        response.message = raw_sql_result
                        response.success = False
                        response.errors.append(f"Error parsing SQL results: {str(e)}")
                        return response.model_dump()
                else:
                    # SQLAgent failed - it didn't return valid JSON with results
                    # The agent's response explains what went wrong (could be DB error, 
                    # query error, or other issues - we don't assume the type)
                    response.success = False
                    response.message = raw_sql_result if raw_sql_result else "Error executing SQL query"
                    response.errors.append("SQLAgent could not complete the query successfully")
                    logger.warning(f"SQLAgent failed - no valid results returned. Response: {raw_sql_result[:200]}...")
                    return response.model_dump()

                # ---------------------------------------------------------
                # STEP 3: VISUALIZATION (VIZ AGENT - Conditional)
                # ---------------------------------------------------------
                if intent == "requiere_visualizacion" and response.sql_data:
                    logger.info("Starting VizAgent (condition met)...")
                    
                    viz_agent = client.create_agent(
                        name="VizAgent",
                        instructions=AgentPrompts.VIZ_AGENT,
                        tools=mcp, 
                    )

                    viz_input = json.dumps(sql_json, indent=2, ensure_ascii=False)
                    start_time = time.time()
                    raw_viz_result = await run_single_agent(viz_agent, viz_input)
                    elapsed_ms = (time.time() - start_time) * 1000
                    viz_json = JSONParser.extract_json(raw_viz_result)

                    agent_logger.log_agent_response(
                        agent_name="VizAgent",
                        raw_response=raw_viz_result,
                        parsed_response=viz_json,
                        input_text=viz_input,
                        execution_time_ms=elapsed_ms,
                    )

                    # Add VizAgent output to response
                    response.agent_outputs.append(AgentOutput(
                        agent_name="VizAgent",
                        raw_response=raw_viz_result,
                        parsed_response=viz_json,
                        execution_time_ms=elapsed_ms,
                        input_text=viz_input,
                    ))

                    if viz_json and "powerbi_url" in viz_json:
                        response.viz_data = VizResult(**viz_json)
                        response.message += f"\nVisualization generated: {response.viz_data.powerbi_url}"
                    else:
                        logger.warning("VizAgent did not return a valid URL.")

                response.success = True

    except Exception as e:
        logger.error(f"Error in workflow: {e}", exc_info=True)
        response.success = False
        response.message = f"System error: {str(e)}"
        response.errors.append(str(e))

    finally:
        agent_logger.end_session(
            success=response.success,
            final_message=response.message,
            errors=response.errors if response.errors else None,
        )
        await credential.close()

    return response.model_dump()

