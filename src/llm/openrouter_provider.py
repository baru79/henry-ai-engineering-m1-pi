from typing import Optional
from src.llm.base import LLMProvider, LLMProviderError


class OpenRouterProvider(LLMProvider):
    """
    Adapter para OpenRouter (acceso a modelos gratuitos Open Source vía API compatible con OpenAI).
    Modelos recomendados con capa gratuita:
    - 'meta-llama/llama-3.3-70b-instruct:free'
    - 'google/gemini-2.0-flash-exp:free'
    - 'meta-llama/llama-3.1-8b-instruct:free'
    """

    def get_default_model(self) -> str:
        return "meta-llama/llama-3.3-70b-instruct:free"

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        try:
            from openai import OpenAI
        except ImportError:
            raise LLMProviderError(
                "La librería 'openai' no está instalada. Ejecutá: pip install openai"
            )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "https://nubbix.ai",
                "X-Title": "Nubbix Triage AI"
            }
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=600,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content or "{}"
        p_tokens = response.usage.prompt_tokens if response.usage else 0
        c_tokens = response.usage.completion_tokens if response.usage else 0

        return content, p_tokens, c_tokens
