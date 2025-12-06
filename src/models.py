"""
Pydantic models for defining data structure between API and Workflow.
"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class IntentResult(BaseModel):
    user_question: str
    intent: str
    tipo_patron: Optional[str] = None  # A, B, C, D, E, F, G, H, I, J, K, L, M, N
    arquetipo: Optional[str] = None  # Comparación, Relación, Proyección, Simulación
    razon: Optional[str] = None

class SQLResult(BaseModel):
    pregunta_original: str
    sql: str
    tablas: List[str] = []
    resultados: List[Dict[str, Any]] = []
    total_filas: int = 0
    resumen: str

class VizResult(BaseModel):
    tipo_grafico: str
    metric_name: str
    data_points: List[Dict[str, Any]]
    powerbi_url: str

class AgentOutput(BaseModel):
    """Output from an individual agent."""
    agent_name: str
    raw_response: str
    parsed_response: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    input_text: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    message: str
    intent: Optional[str] = None
    sql_data: Optional[SQLResult] = None
    viz_data: Optional[VizResult] = None
    agent_outputs: List[AgentOutput] = []  # Outputs from each executed agent
    errors: List[str] = []

