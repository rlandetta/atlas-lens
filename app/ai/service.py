import logging
import os
import time

from app.ai.base import AIProvider
from app.ai.models import AIError, AIRequest, AIResult, CoverageContext, ImageReference
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers import MockProvider

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, provider: AIProvider | None = None, prompt_builder: PromptBuilder | None = None):
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.provider = provider or self._build_provider()

    def generate_narration(self, coverage_id: str, photo_id: str, coverage: dict, photo: dict, simulate_error: bool = False) -> AIResult:
        started_at = time.perf_counter()
        provider_name = getattr(self.provider, "provider_name", "unknown")

        try:
            request = self._build_request(photo_id, coverage, photo, simulate_error)
            result = self.provider.generate_narration(request)
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.info(
                "ai_generation coverage_id=%s photo_id=%s provider=%s duration_ms=%s status=success",
                coverage_id,
                photo_id,
                provider_name,
                duration_ms,
            )
            return result
        except AIError:
            raise
        except Exception as error:
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.warning(
                "ai_generation coverage_id=%s photo_id=%s provider=%s duration_ms=%s status=error",
                coverage_id,
                photo_id,
                provider_name,
                duration_ms,
            )
            raise AIError(
                code="AI_GENERATION_FAILED",
                message="No fue posible generar la narración.",
                status_code=500,
                provider=provider_name,
            ) from error

    def _build_provider(self) -> AIProvider:
        provider_name = os.getenv("AI_PROVIDER", "mock").strip().lower()
        if provider_name == "mock":
            return MockProvider()
        raise AIError(
            code="AI_PROVIDER_NOT_CONFIGURED",
            message="El proveedor de IA configurado no está disponible.",
            status_code=503,
            provider=provider_name,
        )

    def _build_request(self, photo_id: str, coverage: dict, photo: dict, simulate_error: bool) -> AIRequest:
        image = ImageReference(
            photo_id=photo_id,
            filename=str(photo.get("name", "")),
            mime_type=str(photo.get("type", "image/jpeg")),
            size=photo.get("size"),
            width=photo.get("width"),
            height=photo.get("height"),
            data_url=photo.get("data_url"),
        )
        context = CoverageContext(
            title=str(coverage.get("coverage_name", "")),
            city=str(coverage.get("city", "")),
            country=str(coverage.get("country", "")),
            agency=str(coverage.get("agency", "")),
            event_date=str(coverage.get("event_date", "")),
            send_date=str(coverage.get("submit_date", "")),
            photographer=str(coverage.get("photographer", "")),
            known_people=tuple(coverage.get("known_people", ()) or ()),
            event_context=str(coverage.get("event_context", coverage.get("coverage_name", ""))),
        )
        return AIRequest(
            image=image,
            coverage_context=context,
            editorial_instructions=self.prompt_builder.build_editorial_instructions(context, "xinhua"),
            language="es",
            max_words=60,
            template="xinhua",
            simulate_error=simulate_error,
        )
