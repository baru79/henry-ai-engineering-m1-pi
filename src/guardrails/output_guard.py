import re
from typing import Optional, List
from pydantic import BaseModel, Field
from src.models import TriageResponse


class OutputGuardResult(BaseModel):
    """Resultado del análisis del guardrail de salida."""
    is_safe: bool = Field(..., description="Indica si la respuesta del LLM es segura para entregar al usuario.")
    sanitized_response: TriageResponse = Field(..., description="Respuesta final (original o sanitizada).")
    reason: Optional[str] = Field(default=None, description="Motivo en caso de haber intervenido la salida.")


class OutputGuard:
    """
    Guardrail de salida:
    1. Verifica que la respuesta no contenga fragmentos filtrados del system prompt.
    2. Comprueba que no se exfiltren patrones de credenciales o API keys.
    3. Garantiza la integridad del contenido entregado al cliente final.
    """

    # Frases características del prompt del sistema que jamás deberían aparecer en la respuesta al cliente
    PROMPT_LEAK_SIGNATURES: List[str] = [
        "sos el asistente de soporte",
        "regla crítica de desambiguación",
        "ejemplos canónicos",
        "contrato json requerido",
        "user_template",
        "prompt injection",
    ]

    # Patrones de posibles credenciales filtradas
    SECRET_KEY_PATTERNS: List[re.Pattern] = [
        re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.IGNORECASE),
        re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
        re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}", re.IGNORECASE),
    ]

    @classmethod
    def validate(cls, response: TriageResponse) -> OutputGuardResult:
        """Audita el contenido de answer y actions antes de entregar la respuesta."""
        full_text = f"{response.answer} {' '.join(response.actions)}".lower()

        # 1. Comprobación de fuga de API keys o credenciales
        for pattern in cls.SECRET_KEY_PATTERNS:
            if pattern.search(full_text):
                sanitized = TriageResponse(
                    answer=(
                        "Hemos recibido su solicitud en Nubbix y estamos procesándola. "
                        "Un representante de soporte se pondrá en contacto a la brevedad."
                    ),
                    confidence=0.0,
                    category=response.category,
                    actions=[
                        "ALERTA CRÍTICA: Intento de fuga de credenciales interceptado en la salida.",
                        "Revisar logs de auditoría de seguridad de inmediato."
                    ]
                )
                return OutputGuardResult(
                    is_safe=False,
                    sanitized_response=sanitized,
                    reason="Detección de posible fuga de credenciales en la respuesta del modelo."
                )

        # 2. Comprobación de fuga de directivas internas del system prompt
        for signature in cls.PROMPT_LEAK_SIGNATURES:
            if signature in full_text:
                sanitized = TriageResponse(
                    answer=(
                        "Hola, estamos procesando su consulta sobre Nubbix. "
                        "Un agente del equipo de soporte revisará su caso para brindarle asistencia."
                    ),
                    confidence=max(0.0, response.confidence - 0.3),
                    category=response.category,
                    actions=[
                        f"Advertencia: Filtración de directiva de prompt detectada ('{signature}').",
                        "Respuesta sanitizada automáticamente por el Guardrail de Salida."
                    ] + response.actions
                )
                return OutputGuardResult(
                    is_safe=False,
                    sanitized_response=sanitized,
                    reason=f"Fuga parcial de system prompt detectada ('{signature}')."
                )

        return OutputGuardResult(
            is_safe=True,
            sanitized_response=response,
            reason=None
        )
