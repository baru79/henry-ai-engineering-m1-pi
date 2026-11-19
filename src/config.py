import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")


class Settings:
    """
    Configuración centralizada del sistema de triage.
    Lee de variables de entorno y provee valores por defecto seguros.
    """
    ROOT_DIR: Path = ROOT_DIR
    PROMPTS_DIR: Path = ROOT_DIR / "prompts"
    DATA_DIR: Path = ROOT_DIR / "data"
    EVALS_DIR: Path = ROOT_DIR / "evals"

    # Proveedor y modelo por defecto
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    LLM_MODEL: Optional[str] = os.getenv("LLM_MODEL")

    # Claves de API para proveedores gratuitos
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")

    # Versión de prompt
    PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "v2_few_shot").strip()

    # Reintentos automáticos ante error de parsing JSON
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))

    # Extra credit: Caché MD5
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")

    # Archivo de métricas
    METRICS_FILE_PATH: Path = ROOT_DIR / os.getenv("METRICS_FILE_PATH", "data/metrics.jsonl")

    @classmethod
    def get_api_key(cls, provider: str) -> Optional[str]:
        """Obtiene la clave correspondiente al proveedor seleccionado."""
        provider = provider.lower().strip()
        if provider == "groq":
            return cls.GROQ_API_KEY
        elif provider == "gemini":
            return cls.GEMINI_API_KEY
        elif provider == "openrouter":
            return cls.OPENROUTER_API_KEY
        return None

    @classmethod
    def validate_provider_keys(cls, provider: str) -> None:
        """Verifica que el proveedor seleccionado tenga su API key cargada."""
        key = cls.get_api_key(provider)
        if not key:
            raise ValueError(
                f"Falta la clave de API para el proveedor '{provider}'. "
                f"Por favor configurala en tu archivo .env o en el entorno "
                f"(ej: {provider.upper()}_API_KEY)."
            )


settings = Settings()
