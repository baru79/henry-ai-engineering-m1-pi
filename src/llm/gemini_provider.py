from typing import Optional
from src.llm.base import LLMProvider, LLMProviderError


class GeminiProvider(LLMProvider):
    """
    Adapter para Google AI Studio (Gemini).
    Modelos recomendados: 'gemini-1.5-flash', 'gemini-2.0-flash'.
    Soporta tanto el nuevo SDK oficial 'google-genai' como 'google-generativeai'.
    """

    def get_default_model(self) -> str:
        return "gemini-1.5-flash"

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _call_api(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        # Intento 1: SDK moderno 'google-genai'
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            content = response.text or "{}"
            p_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
            c_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
            return content, p_tokens, c_tokens

        except ImportError:
            pass

        # Intento 2: SDK clásico 'google-generativeai'
        try:
            import google.generativeai as legacy_genai

            legacy_genai.configure(api_key=self.api_key)
            model = legacy_genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0.0}
            )
            response = model.generate_content(user_prompt)
            content = response.text or "{}"
            p_tokens = response.usage_metadata.prompt_token_count if hasattr(response, "usage_metadata") and response.usage_metadata else 0
            c_tokens = response.usage_metadata.candidates_token_count if hasattr(response, "usage_metadata") and response.usage_metadata else 0
            return content, p_tokens, c_tokens

        except ImportError:
            raise LLMProviderError(
                "No se encontró ningún SDK de Gemini. Instalá: pip install google-genai"
            )
        except Exception as e:
            raise LLMProviderError(f"Error al llamar a Gemini API: {str(e)}") from e
