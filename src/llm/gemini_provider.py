from src.llm.base import LLMProvider, LLMProviderError


class GeminiProvider(LLMProvider):
    """
    Adapter para Google AI Studio (Gemini).
    Modelos disponibles: 'gemini-2.5-flash', 'gemini-3.8-flash', 'gemini-4-hydrogen', etc.
    Usa el SDK oficial 'google-genai' (>= 3.0).
    """

    # Mapeo de nombres legados a los modelos actuales disponibles en la API.
    _legacy_to_current = {
        "gemini-1.5-flash": "gemini-3.8-flash",
        "gemini-2.0-flash": "gemini-3.8-flash",
    }

    def get_default_model(self) -> str:
        """Modelo por defecto recomendado para Gemini."""
        return "gemini-3.8-flash"

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _resolve_model_name(self) -> str:
        """Traduce nombres legados al modelo actual disponible en la API."""
        return self._legacy_to_current.get(self.model, self.model)

    def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        normalized_model = self._resolve_model_name()

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=normalized_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            content = response.text or "{}"
            p_tokens = (
                response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0
            )
            c_tokens = (
                response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0
            )
            return content, p_tokens, c_tokens

        except ImportError:
            raise LLMProviderError(
                "No se encontró el SDK de Gemini. Instalá: pip install google-genai"
            )
        except Exception as e:
            raise LLMProviderError(f"Error al llamar a Gemini API: {str(e)}") from e
