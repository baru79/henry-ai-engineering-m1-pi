from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from src.config import settings
from src.models import MetricRecord
from src.observability.pricing import PricingCalculator


class MetricsLogger:
    """
    Logger estructurado append-only para observabilidad de cada llamada al servicio.
    Escribe exclusivamente en formato JSONL cumpliendo la rúbrica de entrega.
    """

    @classmethod
    def log_request(
        cls,
        query: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        cached: bool = False,
        status: str = "success",
        file_path: Optional[Path] = None,
    ) -> MetricRecord:
        """
        Crea un MetricRecord, calcula su costo estimado y lo escribe atómicamente en data/metrics.jsonl.
        """
        target_path = file_path or settings.METRICS_FILE_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)

        total_tokens = prompt_tokens + completion_tokens
        cost_usd = PricingCalculator.calculate_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached=cached
        )

        record = MetricRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            query=query,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_seconds=round(latency_seconds, 4),
            cost_usd=cost_usd,
            cached=cached,
            status=status
        )

        with open(target_path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

        return record

    @classmethod
    def load_metrics(cls, file_path: Optional[Path] = None) -> List[MetricRecord]:
        """Lee y parsea todos los registros de métricas existentes."""
        target_path = file_path or settings.METRICS_FILE_PATH
        if not target_path.exists():
            return []

        records = []
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    records.append(MetricRecord.model_validate_json(stripped))
        return records
