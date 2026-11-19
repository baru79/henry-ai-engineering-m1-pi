import re
from typing import Optional, List
from pydantic import BaseModel, Field
from src.models import TriageResponse


class InputGuardResult(BaseModel):
    """Resultado del análisis del guardrail de entrada."""
    is_valid: bool = Field(..., description="Indica si la entrada es válida y segura para ser procesada.")
    sanitized_query: str = Field(..., description="Texto limpio y normalizado.")
    is_adversarial: bool = Field(default=False, description="Indica si se detectó un intento de ataque.")
    reason: Optional[str] = Field(default=None, description="Motivo de rechazo en caso de no ser válida.")


class InputGuard:
    """
    Guardrail de entrada en capas:
    1. Validación estructural (inputs vacíos, longitud mínima y máxima).
    2. Normalización y sanitización básica.
    3. Detección heurística de Prompt Injection y Jailbreaks conocidos.
    """

    MIN_LENGTH: int = 3
    MAX_LENGTH: int = 2500

    # Patrones regex para detectar jailbreaks, bypasses e inyecciones comunes (español e inglés)
    INJECTION_PATTERNS: List[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"ignor[aá]\s+(todas\s+las\s+)?instrucciones(\s+anteriores)?", re.IGNORECASE),
        re.compile(r"olvid[aá]\s+(todo\s+lo\s+anterior|tus\s+instrucciones)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(in\s+)?(DAN|developer|unrestricted|god)\s+mode", re.IGNORECASE),
        re.compile(r"act[uú]a\s+como\s+(un\s+hacker|modo\s+desarrollador|sin\s+restricciones)", re.IGNORECASE),
        re.compile(r"(reveal|print|show|dame|mostrame)\s+(your\s+)?(system\s+prompt|instrucciones\s+del\s+sistema)", re.IGNORECASE),
        re.compile(r"(exfiltrar?|volcar|dump)\s+(base\s+de\s+datos|contraseñas|api\s*keys?)", re.IGNORECASE),
        re.compile(r"(sudo\s+|rm\s+-rf|SELECT\s+\*\s+FROM|<script>)", re.IGNORECASE),
    ]

    @classmethod
    def validate(cls, raw_query: str) -> InputGuardResult:
        """Analiza la consulta cruda y dictamina si es segura y procesable."""
        if not raw_query or not raw_query.strip():
            return InputGuardResult(
                is_valid=False,
                sanitized_query="",
                is_adversarial=False,
                reason="La consulta del cliente está vacía."
            )

        cleaned = raw_query.strip()

        # Validación de longitud
        if len(cleaned) < cls.MIN_LENGTH:
            return InputGuardResult(
                is_valid=False,
                sanitized_query=cleaned,
                is_adversarial=False,
                reason=f"La consulta es demasiado corta (mínimo {cls.MIN_LENGTH} caracteres)."
            )

        if len(cleaned) > cls.MAX_LENGTH:
            return InputGuardResult(
                is_valid=False,
                sanitized_query=cleaned[:cls.MAX_LENGTH],
                is_adversarial=False,
                reason=f"La consulta excede la longitud máxima permitida de {cls.MAX_LENGTH} caracteres."
            )

        # Detección de Prompt Injection
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(cleaned):
                return InputGuardResult(
                    is_valid=False,
                    sanitized_query=cleaned,
                    is_adversarial=True,
                    reason=f"Detección de posible Prompt Injection / Jailbreak (patrón: '{pattern.pattern}')."
                )

        return InputGuardResult(
            is_valid=True,
            sanitized_query=cleaned,
            is_adversarial=False,
            reason=None
        )

    @classmethod
    def create_blocked_response(cls, reason: str) -> TriageResponse:
        """
        Genera una respuesta segura y contenida si la entrada es bloqueada por seguridad.
        Evita gastar tokens de LLM y no compromete el contrato de la API.
        """
        return TriageResponse(
            answer=(
                "Estimado cliente, su consulta contiene expresiones o formatos no admitidos "
                "por nuestras políticas de seguridad. Si necesita asistencia con su cuenta de Nubbix, "
                "por favor describa su consulta operativa de forma puntual."
            ),
            confidence=0.0,
            category="other",
            actions=[
                f"Bloqueo preventivo por Guardrail de Seguridad: {reason}",
                "Verificar actividad inusual en el canal de origen del ticket"
            ]
        )
