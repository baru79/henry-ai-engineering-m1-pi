from typing import Dict, Optional, Type
from src.config import settings
from src.llm.base import LLMProvider
from src.llm.groq_provider import GroqProvider
from src.llm.gemini_provider import GeminiProvider
from src.llm.openrouter_provider import OpenRouterProvider


class LLMFactory:
    """
    Factory Pattern para instanciar proveedores de LLM de forma desacoplada.
    Permite alternar entre proveedores sin modificar la lógica de negocio del triage.
    """

    _REGISTRY: Dict[str, Type[LLMProvider]] = {
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
    }

    @classmethod
    def list_supported_providers(cls) -> list[str]:
        return list(cls._REGISTRY.keys())

    @classmethod
    def create(
        cls,
        provider_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> LLMProvider:
        """
        Crea e inicializa una instancia de LLMProvider.
        Si no se especifican provider o model, toma los configurados en settings / .env.
        """
        provider_key = (provider_name or settings.LLM_PROVIDER).lower().strip()

        provider_cls = cls._REGISTRY.get(provider_key)
        if not provider_cls:
            valid_providers = ", ".join(cls._REGISTRY.keys())
            raise ValueError(
                f"Proveedor '{provider_key}' no soportado. "
                f"Opciones disponibles: [{valid_providers}]."
            )

        # Validar existencia de API Key
        settings.validate_provider_keys(provider_key)
        api_key = settings.get_api_key(provider_key)

        # Si model es None, el provider usará su default_model, salvo que settings.LLM_MODEL esté fijado
        chosen_model = model or settings.LLM_MODEL

        return provider_cls(api_key=api_key, model=chosen_model)
