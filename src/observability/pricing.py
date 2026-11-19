from typing import Dict, Tuple

# Tarifas oficiales de referencia por cada 1.000.000 de tokens (en USD)
# Formato: "nombre_modelo": (costo_input_por_1M, costo_output_por_1M)
MODEL_PRICING_PER_MILLION: Dict[str, Tuple[float, float]] = {
    # Groq / Llama
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-70b-versatile": (0.59, 0.79),

    # Google Gemini
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),

    # OpenRouter Free / Open Source models
    "meta-llama/llama-3.3-70b-instruct:free": (0.59, 0.79),
    "meta-llama/llama-3.1-8b-instruct:free": (0.05, 0.08),
    "google/gemini-2.0-flash-exp:free": (0.075, 0.30),

    # Tarifa de fallback genérica
    "default": (0.10, 0.30),
}


class PricingCalculator:
    """
    Calculadora transparente y auditable de costos estimados en USD por request.
    Permite reproducir el costo exacto a partir de los tokens de entrada y salida.
    """

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached: bool = False
    ) -> float:
        """
        Calcula el costo total en USD.
        Si la respuesta proviene de la caché MD5, el costo de inferencia es estrictamente $0.00.
        """
        if cached:
            return 0.0

        # Normalizar nombre del modelo
        normalized_model = model.lower().strip()
        pricing = MODEL_PRICING_PER_MILLION.get(normalized_model, MODEL_PRICING_PER_MILLION["default"])

        input_rate_per_token = pricing[0] / 1_000_000.0
        output_rate_per_token = pricing[1] / 1_000_000.0

        cost = (prompt_tokens * input_rate_per_token) + (completion_tokens * output_rate_per_token)
        return round(cost, 7)
