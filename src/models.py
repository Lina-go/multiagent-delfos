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
    run_id: Optional[str] = None
    image_base64: Optional[str] = None  # Base64 encoded chart image
    image_url: Optional[str] = None  # URL to the chart image

class AgentOutput(BaseModel):
    """Output from an individual agent."""
    agent_name: str
    raw_response: str
    parsed_response: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    input_text: Optional[str] = None

class FormattedResponse(BaseModel):
    """Structured response from FormatAgent."""
    patron: str  # e.g., "comparacion", "relacion", etc.
    datos: List[Dict[str, Any]]  # SQL results
    arquetipo: str  # A-N
    visualizacion: str  # "YES" | "NO"
    tipo_grafica: Optional[str] = None  # "line" | "bar" | "pie" | "stackedbar" | None
    imagen: Optional[str] = None  # base64 string or None
    link_power_bi: Optional[str] = None  # Power BI URL or None
    insight: Optional[str] = None  # Generated analysis or None

class ChatResponse(BaseModel):
    success: bool
    message: str
    intent: Optional[str] = None
    sql_data: Optional[SQLResult] = None
    viz_data: Optional[VizResult] = None
    formatted_response: Optional[FormattedResponse] = None
    agent_outputs: List[AgentOutput] = []  # Outputs from each executed agent
    errors: List[str] = []

