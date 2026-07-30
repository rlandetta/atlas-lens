import random
import time

from app.ai.base import AIProvider
from app.ai.models import AIRequest, AIResult


class MockProvider(AIProvider):
    provider_name = "mock"
    model_name = "mock-editorial-v1"

    def generate_narration(self, request: AIRequest) -> AIResult:
        if request.simulate_error:
            time.sleep(0.5)
            raise RuntimeError("Simulated mock provider failure.")

        time.sleep(random.uniform(0.5, 1.0))

        context = request.coverage_context
        filename = request.image.filename
        event_context = context.event_context or context.title or "la cobertura seleccionada"
        narration = (
            "Una persona participa durante una actividad pública relacionada "
            f"con {event_context}, según la fotografía {filename}."
        )

        return AIResult(
            narration=self._limit_words(narration, request.max_words),
            provider=self.provider_name,
            model=self.model_name,
            status="success",
            warnings=[
                "Narración simulada: revisar nombres, cargos y contexto antes de aprobar."
            ],
            raw_metadata={
                "source": "mock",
                "filename": filename,
            },
        )

    @staticmethod
    def _limit_words(value: str, max_words: int) -> str:
        words = value.split()
        if len(words) <= max_words:
            return value
        return " ".join(words[:max_words]).rstrip(".,;:") + "."
