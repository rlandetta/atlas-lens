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
        subject = context.known_people[0] if context.known_people else "Una persona"
        organization = context.organizations[0] if context.organizations else ""
        city_phrase = f" en {context.city}" if context.city else ""
        coverage_title = context.coverage_title or "la cobertura seleccionada"
        organization_phrase = f" vinculada con {organization}" if organization else ""
        narration = (
            f"{subject} participa en una actividad pública{organization_phrase}{city_phrase}, "
            f"relacionada con {coverage_title}, según la fotografía {filename}."
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
                "known_people": list(context.known_people),
                "organizations": list(context.organizations),
                "keywords": list(context.keywords),
            },
        )

    @staticmethod
    def _limit_words(value: str, max_words: int) -> str:
        words = value.split()
        if len(words) <= max_words:
            return value
        return " ".join(words[:max_words]).rstrip(".,;:") + "."
