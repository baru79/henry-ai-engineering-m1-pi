from typing import List, Literal
from pydantic import BaseModel, Field


# Categorías oficiales requeridas para Nubbix
TicketCategory = Literal["billing", "technical", "account", "other"]


class TriageResponse(BaseModel):
    """
    Contrato estricto exigido por Nubbix para la respuesta de triage.
    Cualquier respuesta del LLM debe validarse contra este esquema Pydantic.
    """
    answer: str = Field(
        ...,
        description="Respuesta profesional, empática y contextualizada propuesta al cliente."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de certeza del modelo en su clasificación (entre 0.0 y 1.0)."
    )
    category: TicketCategory = Field(
        ...,
        description="Categoría del ticket. Debe ser estrictamente una de: billing, technical, account, other."
    )
    actions: List[str] = Field(
        ...,
        min_length=1,
        description="Lista de acciones recomendadas para el agente humano de soporte de Nubbix."
    )


class MetricRecord(BaseModel):
    """
    Estructura del registro append-only de observabilidad para data/metrics.jsonl.
    """
    timestamp: str = Field(..., description="Fecha y hora de la solicitud en formato ISO 8601.")
    query: str = Field(..., description="Texto de la consulta del ticket.")
    provider: str = Field(..., description="Proveedor de LLM utilizado (groq, gemini, openrouter).")
    model: str = Field(..., description="Nombre del modelo ejecutado.")
    prompt_tokens: int = Field(default=0, ge=0, description="Tokens consumidos en el prompt.")
    completion_tokens: int = Field(default=0, ge=0, description="Tokens consumidos en la generación.")
    total_tokens: int = Field(default=0, ge=0, description="Tokens totales consumidos.")
    latency_seconds: float = Field(..., ge=0.0, description="Tiempo total de procesamiento en segundos.")
    cost_usd: float = Field(..., ge=0.0, description="Costo estimado en dólares estadounidenses.")
    cached: bool = Field(default=False, description="Indica si la respuesta provino de la caché MD5.")
    status: str = Field(default="success", description="Estado de la ejecución: success, retry, blocked, error.")
