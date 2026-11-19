import time
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """
    Respuesta estandarizada emitida por cualquier proveedor de LLM.
    Desacopla la lógica de negocio de los formatos dispares de cada SDK.
    """
    content: str = Field(..., description="Texto generado por el modelo (esperado en formato JSON).")
    prompt_tokens: int = Field(default=0, ge=0, description="Tokens consumidos en el prompt de entrada.")
    completion_tokens: int = Field(default=0, ge=0, description="Tokens consumidos en la generación.")
    total_tokens: int = Field(default=0, ge=0, description="Suma total de tokens.")
    latency_seconds: float = Field(..., ge=0.0, description="Tiempo de respuesta en segundos.")
    model: str = Field(..., description="Nombre del modelo que ejecutó la inferencia.")
    provider: str = Field(..., description="Nombre del proveedor (groq, gemini, openrouter).")


class LLMProviderError(Exception):
    """Excepción base para errores de comunicación, autenticación o límites de cuota de LLM."""
    pass


class LLMProvider(ABC):
    """
    Clase abstracta base para la integración multi-proveedor.
    Cualquier nuevo proveedor (Groq, Gemini, OpenRouter, etc.) debe heredar de esta clase.
    """

    def __init__(self, api_key: str, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or self.get_default_model()

    @abstractmethod
    def get_default_model(self) -> str:
        """Retorna el modelo por defecto recomendado para este proveedor."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nombre identificador del proveedor."""
        pass

    @abstractmethod
    def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        """
        Llamada de bajo nivel a la API.
        Debe retornar una tupla: (texto_generado, prompt_tokens, completion_tokens).
        """
        pass

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Ejecuta la inferencia, mide la latencia de forma transparente y retorna LLMResponse.
        """
        start_time = time.perf_counter()
        try:
            content, p_tokens, c_tokens = self._call_api(system_prompt, user_prompt)
        except Exception as e:
            raise LLMProviderError(f"Error en proveedor '{self.provider_name}' ({self.model}): {str(e)}") from e

        latency = time.perf_counter() - start_time
        total_tokens = p_tokens + c_tokens

        return LLMResponse(
            content=content,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=total_tokens,
            latency_seconds=round(latency, 4),
            model=self.model,
            provider=self.provider_name
        )
