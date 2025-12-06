"""
Multi-agent workflow orchestrator with conditional logic.
"""
import asyncio
import logging
import json
import time
from typing import Dict, Any

from azure.identity.aio import DefaultAzureCredential
from agent_framework import MCPStreamableHTTPTool, ConcurrentBuilder
from agent_framework_azure_ai import AzureAIAgentClient

from src.config.settings import get_settings
from src.config.prompts import AgentPrompts
from src.models import ChatResponse, SQLResult, VizResult, AgentOutput, FormattedResponse
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
            
            # ---------------------------------------------------------
            # STEP 1 & 2: INTENT DETECTION AND SQL GENERATION (PARALLEL)
            # ---------------------------------------------------------
            logger.info("Executing IntentAgent and SQLAgent in parallel using ConcurrentBuilder...")
            
            # Create both agents and execute in parallel using ConcurrentBuilder
            async with AzureAIAgentClient(
                project_endpoint=settings.azure_ai_project_endpoint,
                model_deployment_name=settings.intent_agent_model,
                async_credential=credential,
            ) as intent_client:
                async with AzureAIAgentClient(
                    project_endpoint=settings.azure_ai_project_endpoint,
                    model_deployment_name=settings.sql_agent_model,
                    async_credential=credential,
                ) as sql_client:
                    intent_agent = intent_client.create_agent(
                        name="IntentAgent",
                        instructions=AgentPrompts.INTENT_AGENT,
                    )
                    sql_agent = sql_client.create_agent(
                        name="SQLAgent",
                        instructions=AgentPrompts.SQL_AGENT,
                        tools=mcp,
                    )
                    
                    # Build concurrent workflow
                    workflow = ConcurrentBuilder().participants([intent_agent, sql_agent]).build()
                    
                    # Execute both agents in parallel with the same input
                    parallel_start_time = time.time()
                    from agent_framework import WorkflowOutputEvent, ChatMessage
                    messages = []
                    async for event in workflow.run_stream(message):
                        if isinstance(event, WorkflowOutputEvent):
                            if hasattr(event, "data"):
                                for msg in event.data:
                                    if hasattr(msg, "text") and msg.text:
                                        messages.append(msg)
                    parallel_elapsed_ms = (time.time() - parallel_start_time) * 1000
                    
                    # Extract results from messages
                    if not messages:
                        logger.error("Concurrent workflow did not return any messages")
                        response.success = False
                        response.message = "Error: Concurrent workflow did not return any messages"
                        response.errors.append("Concurrent workflow did not return any messages")
                        return response.model_dump()
                    
                    # Find messages from each agent by author_name
                    raw_intent = ""
                    raw_sql_result = ""
                    for msg in messages:
                        if hasattr(msg, "author_name") and hasattr(msg, "text"):
                            if msg.author_name == "IntentAgent":
                                raw_intent = msg.text
                            elif msg.author_name == "SQLAgent":
                                raw_sql_result = msg.text
                    
                    # Fallback: if author_name doesn't work, use order (first = IntentAgent, second = SQLAgent)
                    if not raw_intent or not raw_sql_result:
                        text_messages = [msg.text for msg in messages if hasattr(msg, "text") and msg.text]
                        if len(text_messages) >= 2:
                            raw_intent = text_messages[0]
                            raw_sql_result = text_messages[1]
                        elif len(text_messages) == 1:
                            # Only one result, try to identify which one
                            raw_intent = text_messages[0]
                            raw_sql_result = text_messages[0]
                    
                    # Process IntentAgent results
                    intent_data = JSONParser.extract_json(raw_intent)
                    intent_elapsed_ms = parallel_elapsed_ms  # Both took the same time
                    
                    agent_logger.log_agent_response(
                        agent_name="IntentAgent",
                        raw_response=raw_intent,
                        parsed_response=intent_data,
                        input_text=message,
                        execution_time_ms=intent_elapsed_ms,
                    )
                    
                    response.agent_outputs.append(AgentOutput(
                        agent_name="IntentAgent",
                        raw_response=raw_intent,
                        parsed_response=intent_data,
                        execution_time_ms=intent_elapsed_ms,
                        input_text=message,
                    ))
                    
                    intent = intent_data.get("intent", "nivel_puntual")
                    response.intent = intent
                    logger.info(f"Intent detected: {intent}")
                    
                    # Process SQLAgent results
                    sql_json = JSONParser.extract_json(raw_sql_result)
                    sql_elapsed_ms = parallel_elapsed_ms  # Both took the same time
                    
                    agent_logger.log_agent_response(
                        agent_name="SQLAgent",
                        raw_response=raw_sql_result,
                        parsed_response=sql_json,
                        input_text=message,
                        execution_time_ms=sql_elapsed_ms,
                    )
                    
                    response.agent_outputs.append(AgentOutput(
                        agent_name="SQLAgent",
                        raw_response=raw_sql_result,
                        parsed_response=sql_json,
                        execution_time_ms=sql_elapsed_ms,
                        input_text=message,
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
                
                async with AzureAIAgentClient(
                    project_endpoint=settings.azure_ai_project_endpoint,
                    model_deployment_name=settings.viz_agent_model,
                    async_credential=credential,
                ) as viz_client:
                    viz_agent = viz_client.create_agent(
                        name="VizAgent",
                        instructions=AgentPrompts.VIZ_AGENT,
                        tools=mcp, 
                    )

                    # Include user_id in the input for VizAgent
                    viz_input_data = {
                        "user_id": user_id,
                        "sql_results": sql_json,
                        "original_question": message,
                    }
                    viz_input = json.dumps(viz_input_data, indent=2, ensure_ascii=False)
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
                        # Validate that the URL is not a placeholder
                        powerbi_url = viz_json.get("powerbi_url", "")
                        if not powerbi_url.startswith("https://") or "URL_GENERADO" in powerbi_url or "URL_REAL" in powerbi_url:
                            logger.warning(
                                f"VizAgent returned a placeholder URL instead of a real one: {powerbi_url}. "
                                "The agent may not have called the MCP tools correctly."
                            )
                        response.viz_data = VizResult(**viz_json)
                    else:
                        logger.warning("VizAgent did not return a valid URL.")

            # ---------------------------------------------------------
            # STEP 3.5: GRAPH EXECUTION (GRAPH EXECUTOR - Conditional)
            # ---------------------------------------------------------
            if response.viz_data and response.viz_data.run_id and response.viz_data.tipo_grafico:
                logger.info("Starting GraphExecutor to generate chart image...")
                
                # Prepare input for GraphExecutor (already prepared, but ensure it's ready)
                graph_input_data = {
                    "run_id": response.viz_data.run_id,
                    "tipo_grafico": response.viz_data.tipo_grafico,
                    "data_points": response.viz_data.data_points,
                }
                graph_input = json.dumps(graph_input_data, indent=2, ensure_ascii=False)
                
                # Create MCP connection for chart server
                async with MCPStreamableHTTPTool(
                    name="chart-mcp",
                    url=settings.mcp_chart_server_url,
                    timeout=settings.mcp_timeout,
                    sse_read_timeout=settings.mcp_sse_timeout,
                    approval_mode="never_require",
                ) as chart_mcp:
                    async with AzureAIAgentClient(
                        project_endpoint=settings.azure_ai_project_endpoint,
                        model_deployment_name=settings.graph_executor_model,
                        async_credential=credential,
                    ) as graph_client:
                        graph_agent = graph_client.create_agent(
                            name="GraphExecutor",
                            instructions=AgentPrompts.GRAPH_EXECUTOR_AGENT,
                            tools=chart_mcp,
                        )
                        
                        # Execute GraphExecutor
                        start_time = time.time()
                        raw_graph_result = await run_single_agent(graph_agent, graph_input)
                        elapsed_ms = (time.time() - start_time) * 1000
                        graph_json = JSONParser.extract_json(raw_graph_result)
                        
                        agent_logger.log_agent_response(
                            agent_name="GraphExecutor",
                            raw_response=raw_graph_result,
                            parsed_response=graph_json,
                            input_text=graph_input,
                            execution_time_ms=elapsed_ms,
                        )
                        
                        # Add GraphExecutor output to response
                        response.agent_outputs.append(AgentOutput(
                            agent_name="GraphExecutor",
                            raw_response=raw_graph_result,
                            parsed_response=graph_json,
                            execution_time_ms=elapsed_ms,
                            input_text=graph_input,
                        ))
                        
                        # GraphExecutor retorna image_url, guardar directamente
                        if graph_json and "image_url" in graph_json:
                            image_url = graph_json["image_url"]
                            response.viz_data.image_url = image_url
                            logger.info(f"GraphExecutor returned image URL: {image_url[:100]}...")
                        else:
                            logger.warning("GraphExecutor did not return a valid image_url")

            # ---------------------------------------------------------
            # STEP 4: FORMAT RESPONSE (FORMAT AGENT - Always runs if successful)
            # ---------------------------------------------------------
            if response.success and response.sql_data:
                logger.info("Starting FormatAgent to generate user-friendly message...")
                
                # Prepare input for FormatAgent with all available data (prepared in advance)
                format_input_data = {
                    "pregunta_original": message,
                    "intent": intent,
                    "tipo_patron": intent_data.get("tipo_patron"),
                    "arquetipo": intent_data.get("arquetipo"),
                    "sql_data": {
                        "pregunta_original": response.sql_data.pregunta_original,
                        "sql": response.sql_data.sql,
                        "tablas": response.sql_data.tablas,
                        "resultados": response.sql_data.resultados,
                        "total_filas": response.sql_data.total_filas,
                        "resumen": response.sql_data.resumen,
                    }
                }
                
                if response.viz_data:
                    format_input_data["viz_data"] = {
                        "tipo_grafico": response.viz_data.tipo_grafico,
                        "metric_name": response.viz_data.metric_name,
                        "data_points": response.viz_data.data_points,
                        "powerbi_url": response.viz_data.powerbi_url,
                        "run_id": response.viz_data.run_id,
                        "image_url": response.viz_data.image_url,
                    }

                format_input = json.dumps(format_input_data, indent=2, ensure_ascii=False)
                
                async with AzureAIAgentClient(
                    project_endpoint=settings.azure_ai_project_endpoint,
                    model_deployment_name=settings.format_agent_model,
                    async_credential=credential,
                ) as format_client:
                    format_agent = format_client.create_agent(
                        name="FormatAgent",
                        instructions=AgentPrompts.FORMAT_AGENT,
                    )
                    start_time = time.time()
                    formatted_message = await run_single_agent(format_agent, format_input)
                    elapsed_ms = (time.time() - start_time) * 1000

                    # Parse the JSON response from FormatAgent
                    formatted_json = JSONParser.extract_json(formatted_message)
                    
                    agent_logger.log_agent_response(
                        agent_name="FormatAgent",
                        raw_response=formatted_message,
                        parsed_response=formatted_json,
                        input_text=format_input,
                        execution_time_ms=elapsed_ms,
                    )

                    # Add FormatAgent output to response
                    response.agent_outputs.append(AgentOutput(
                        agent_name="FormatAgent",
                        raw_response=formatted_message,
                        parsed_response=formatted_json,
                        execution_time_ms=elapsed_ms,
                        input_text=format_input,
                    ))

                    # Create FormattedResponse from parsed JSON
                    if formatted_json:
                        try:
                            response.formatted_response = FormattedResponse(**formatted_json)
                            logger.info("FormatAgent generated structured response")
                        except Exception as e:
                            logger.warning(f"Error parsing FormattedResponse: {e}")
                            # Fallback to old behavior
                            formatted_message = formatted_message.strip()
                            if formatted_message.startswith("```"):
                                lines = formatted_message.split("\n")
                                formatted_message = "\n".join(lines[1:-1]) if len(lines) > 2 else formatted_message
                            response.message = formatted_message if formatted_message else response.sql_data.resumen
                    else:
                        # Fallback if JSON parsing fails
                        formatted_message = formatted_message.strip()
                        if formatted_message.startswith("```"):
                            lines = formatted_message.split("\n")
                            formatted_message = "\n".join(lines[1:-1]) if len(lines) > 2 else formatted_message
                        response.message = formatted_message if formatted_message else response.sql_data.resumen
                        logger.warning("FormatAgent did not return valid JSON, using fallback")

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
