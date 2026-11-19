import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
from src.config import settings
from src.models import TriageResponse


class MD5ResponseCache:
    """
    Extra Credit: Caché basada en Hash MD5 de la consulta.
    Optimiza el soporte de Nubbix evitando invocar al LLM en consultas idénticas (60% del volumen diario).
    Persiste en disco en data/cache.json para mantener vigencia entre ejecuciones de CLI.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or (settings.DATA_DIR / "cache.json")
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _normalize_query(self, query: str) -> str:
        """Normaliza el texto: minúsculas, espacios colapsados y sin signos extremos."""
        normalized = query.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _generate_key(self, query: str, prompt_version: str) -> str:
        """
        Genera el hash MD5 combinando la versión del prompt y la consulta normalizada.
        Garantiza que si cambia la versión del prompt, no se use una respuesta desactualizada.
        """
        normalized_query = self._normalize_query(query)
        payload = f"{prompt_version.strip()}:{normalized_query}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _load_cache(self) -> None:
        """Carga el contenido de la caché desde el archivo JSON si existe."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._memory_cache = json.load(f)
            except Exception:
                self._memory_cache = {}
        else:
            self._memory_cache = {}

    def _persist_cache(self) -> None:
        """Guarda la caché en disco de forma segura."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, query: str, prompt_version: str) -> Optional[TriageResponse]:
        """
        Recupera la respuesta cacheada si la caché está habilitada y existe el hash MD5.
        """
        if not settings.CACHE_ENABLED:
            return None

        key = self._generate_key(query, prompt_version)
        entry = self._memory_cache.get(key)
        if entry:
            try:
                return TriageResponse.model_validate(entry.get("response"))
            except Exception:
                return None
        return None

    def set(self, query: str, prompt_version: str, response: TriageResponse) -> None:
        """Guarda una respuesta válida en la caché asociada al hash MD5."""
        if not settings.CACHE_ENABLED:
            return

        key = self._generate_key(query, prompt_version)
        self._memory_cache[key] = {
            "query": query.strip(),
            "prompt_version": prompt_version,
            "response": response.model_dump()
        }
        self._persist_cache()

    def clear(self) -> None:
        """Limpia la memoria y elimina el archivo de caché."""
        self._memory_cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()


# Instancia singleton para ser reutilizada en la aplicación
response_cache = MD5ResponseCache()
