"""
src/backend/schemas.py
Modelos Pydantic para definir la estructura de datos entre el API y el Workflow.
"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "anonymous"

class IntentResult(BaseModel):
    user_question: str
    intent: str
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

class ChatResponse(BaseModel):
    success: bool
    message: str
    intent: Optional[str] = None
    sql_data: Optional[SQLResult] = None
    viz_data: Optional[VizResult] = None
    errors: List[str] = []