from typing import Optional
from src.llm.base import LLMProvider, LLMProviderError


class GroqProvider(LLMProvider):
    """
    Adapter para Groq Cloud (ultra rápido y gratuito).
    Modelos oficiales soportados:
    - 'openai/gpt-oss-120b'
    - 'openai/gpt-oss-20b'
    - 'openai/gpt-oss-safeguard-20b'
    """

    def get_default_model(self) -> str:
        return "openai/gpt-oss-120b"

    @property
    def provider_name(self) -> str:
        return "groq"

    def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        try:
            from groq import Groq
        except ImportError:
            raise LLMProviderError(
                "La librería 'groq' no está instalada. Ejecutá: pip install groq"
            )

        client = Groq(api_key=self.api_key)

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
