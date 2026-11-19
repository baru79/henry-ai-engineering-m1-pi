from pathlib import Path
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field
from src.config import settings


class PromptTemplate(BaseModel):
    """Representa un template de prompt versionado cargado desde YAML."""
    version: str = Field(..., description="Identificador de la versión (ej: v1_zero_shot, v2_few_shot).")
    description: str = Field(..., description="Descripción del enfoque de context engineering empleado.")
    system_prompt: str = Field(..., description="Instrucción del sistema.")
    user_template: str = Field(..., description="Template con marcador {query} para el input del usuario.")

    def render_user_prompt(self, query: str) -> str:
        """Sustituye la variable {query} por el texto real de la consulta del cliente."""
        return self.user_template.replace("{query}", query.strip())


class PromptLoader:
    """Manejador para cargar y versionar prompts externos."""

    @classmethod
    def list_available_prompts(cls) -> List[str]:
        """Lista las versiones de prompts encontradas en prompts/."""
        if not settings.PROMPTS_DIR.exists():
            return []
        return [f.stem for f in settings.PROMPTS_DIR.glob("*.yaml")]

    @classmethod
    def load(cls, version: Optional[str] = None) -> PromptTemplate:
        """
        Carga el archivo YAML correspondiente a la versión especificada
        o a la versión configurada en settings.PROMPT_VERSION.
        """
        chosen_version = (version or settings.PROMPT_VERSION).strip()
        yaml_path = settings.PROMPTS_DIR / f"{chosen_version}.yaml"

        if not yaml_path.exists():
            available = cls.list_available_prompts()
            raise FileNotFoundError(
                f"No se encontró el archivo de prompt '{chosen_version}.yaml' en {settings.PROMPTS_DIR}. "
                f"Versiones disponibles: {available}"
            )

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"El archivo '{yaml_path}' no contiene un documento YAML válido.")

        return PromptTemplate(
            version=data.get("version", chosen_version),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", "").strip(),
            user_template=data.get("user_template", "{query}").strip(),
        )
