import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from pydantic import ValidationError

# Asegurar que la raíz del proyecto esté en sys.path para ejecuciones directas
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import settings
from src.models import TriageResponse, MetricRecord
from src.llm.factory import LLMFactory
from src.llm.base import LLMResponse, LLMProviderError
from src.prompt_loader import PromptLoader
from src.guardrails import InputGuard, OutputGuard
from src.cache import response_cache
from src.observability import MetricsLogger


class TriageService:
    """
    Servicio orquestador del pipeline de triage inteligente de Nubbix.
    Diseñado para ser reutilizado tanto por la CLI interactiva como por el runner de evals.
    """

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        use_cache: bool = True
    ):
        self.provider_name = provider_name or settings.LLM_PROVIDER
        self.model_name = model_name or settings.LLM_MODEL
        self.prompt_version = prompt_version or settings.PROMPT_VERSION
        self.use_cache = use_cache and settings.CACHE_ENABLED

    def _extract_json_block(self, raw_text: str) -> str:
        """
        Limpia bloques de código markdown (```json ... ```) si el modelo los incluye.
        """
        text = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _parse_and_validate(self, raw_content: str) -> TriageResponse:
        """Parsea y valida la respuesta del LLM contra el esquema Pydantic."""
        cleaned_json = self._extract_json_block(raw_content)
        data = json.loads(cleaned_json)
        return TriageResponse.model_validate(data)

    def process_ticket(self, raw_query: str) -> Tuple[TriageResponse, MetricRecord]:
        """
        Ejecuta el pipeline completo de triage:
        1. Guardrail de entrada (seguridad y sanitización)
        2. Caché MD5 (optimización para consultas repetitivas)
        3. Inferencia LLM con reintento automático ante errores de parsing
        4. Guardrail de salida (prevención de fugas)
        5. Observabilidad (registro en data/metrics.jsonl)
        """
        start_time = time.perf_counter()

        # 1. Guardrail de Entrada
        input_check = InputGuard.validate(raw_query)
        if not input_check.is_valid:
            latency = time.perf_counter() - start_time
            blocked_resp = InputGuard.create_blocked_response(input_check.reason or "Entrada inválida")
            status = "blocked" if input_check.is_adversarial else "invalid_input"

            metric = MetricsLogger.log_request(
                query=raw_query,
                provider="guardrail",
                model="input_guard",
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
                cached=False,
                status=status
            )
            return blocked_resp, metric

        sanitized_query = input_check.sanitized_query

        # 2. Búsqueda en Caché MD5 (Extra Credit)
        if self.use_cache:
            cached_response = response_cache.get(sanitized_query, self.prompt_version)
            if cached_response:
                latency = time.perf_counter() - start_time
                metric = MetricsLogger.log_request(
                    query=sanitized_query,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_seconds=latency,
                    cached=True,
                    status="success"
                )
                return cached_response, metric

        # 3. Cargar Prompt versionado
        prompt_template = PromptLoader.load(self.prompt_version)
        system_prompt = prompt_template.system_prompt
        user_prompt = prompt_template.render_user_prompt(sanitized_query)

        # 4. Inicializar Proveedor LLM
        provider = LLMFactory.create(self.provider_name, self.model_name)
        active_model = provider.model

        # Variables de control para el Retry Loop
        attempt = 0
        max_attempts = settings.MAX_RETRIES + 1
        last_error = ""
        total_p_tokens = 0
        total_c_tokens = 0
        current_user_prompt = user_prompt
        final_triage: Optional[TriageResponse] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                llm_response: LLMResponse = provider.generate(system_prompt, current_user_prompt)
                total_p_tokens += llm_response.prompt_tokens
                total_c_tokens += llm_response.completion_tokens

                # Validar contrato JSON con Pydantic
                final_triage = self._parse_and_validate(llm_response.content)
                break  # Éxito, salir del loop

            except (json.JSONDecodeError, ValidationError) as parse_err:
                last_error = f"Error de contrato/parsing: {str(parse_err)}"
                if attempt < max_attempts:
                    # Retry automático agregando feedback correctivo en el mensaje de usuario
                    current_user_prompt = (
                        f"{user_prompt}\n\n"
                        f"[AVISO DE CORRECCIÓN AUTOMÁTICA]: Tu respuesta anterior no cumplió el contrato JSON o falló la validación Pydantic.\n"
                        f"Error detectado: {str(parse_err)}\n"
                        f"Por favor responde ÚNICAMENTE con el objeto JSON estricto sin texto adicional."
                    )
            except LLMProviderError as api_err:
                # Errores irrecuperables de API
                raise api_err

        if not final_triage:
            # Fallback defensivo si se agotaron los reintentos
            final_triage = TriageResponse(
                answer="Disculpas, tuvimos un inconveniente técnico al procesar su solicitud. Un agente humano de Nubbix lo atenderá en breve.",
                confidence=0.0,
                category="other",
                actions=[f"Revisar fallo recurrente de parsing JSON en modelo {active_model}: {last_error}"]
            )

        # 5. Guardrail de Salida
        output_check = OutputGuard.validate(final_triage)
        final_triage = output_check.sanitized_response

        # 6. Almacenar en Caché MD5 si fue exitoso
        if self.use_cache and output_check.is_safe:
            response_cache.set(sanitized_query, self.prompt_version, final_triage)

        # 7. Registrar Métrica (Observabilidad)
        latency = time.perf_counter() - start_time
        status_code = "retry_success" if attempt > 1 else "success"

        metric = MetricsLogger.log_request(
            query=sanitized_query,
            provider=self.provider_name,
            model=active_model,
            prompt_tokens=total_p_tokens,
            completion_tokens=total_c_tokens,
            latency_seconds=latency,
            cached=False,
            status=status_code
        )

        return final_triage, metric


def main():
    parser = argparse.ArgumentParser(
        description="Nubbix Triage AI - Servicio de clasificación y respuesta automatizada de tickets."
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Texto de la consulta del cliente (ticket de soporte)."
    )
    parser.add_argument(
        "--provider", "-p",
        type=str,
        default=None,
        help="Proveedor de LLM a utilizar ('groq', 'gemini', 'openrouter'). Por defecto lee de .env."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Modelo específico a utilizar (ej: 'openai/gpt-oss-120b', 'gemini-1.5-flash')."
    )
    parser.add_argument(
        "--prompt-version", "-v",
        type=str,
        default=None,
        help="Versión del prompt a utilizar ('v1_zero_shot', 'v2_few_shot')."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Desactiva temporalmente el uso de la caché MD5."
    )

    args = parser.parse_args()

    # Si no se pasó --query por flag, pedirla interactivamente
    query_text = args.query
    if not query_text:
        print("\n=== Nubbix Triage AI (Nivel 1 de Soporte) ===")
        print("Ingresá la consulta del ticket de cliente (o presioná Ctrl+C para salir):")
        try:
            query_text = input("> ").strip()
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            sys.exit(0)

    if not query_text:
        print("Error: La consulta no puede estar vacía.", file=sys.stderr)
        sys.exit(1)

    try:
        service = TriageService(
            provider_name=args.provider,
            model_name=args.model,
            prompt_version=args.prompt_version,
            use_cache=not args.no_cache
        )

        response, metric = service.process_ticket(query_text)

        # Imprimir JSON validado por stdout (estrictamente el contrato pedido en consigna)
        print("\n" + json.dumps(response.model_dump(), indent=2, ensure_ascii=False))

        # Resumen breve de observabilidad en stderr para no ensuciar la salida JSON si se pipea
        print(
            f"\n[Métricas] Proveedor: {metric.provider} | Modelo: {metric.model} | "
            f"Latencia: {metric.latency_seconds:.3f}s | Tokens: {metric.total_tokens} | "
            f"Costo est.: ${metric.cost_usd:.6f} USD | Caché: {metric.cached}",
            file=sys.stderr
        )

    except Exception as e:
        print(f"\n[ERROR FATAL]: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
