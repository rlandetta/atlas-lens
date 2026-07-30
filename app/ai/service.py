import logging
import time

from app.ai.base import AIProvider
from app.ai.context_engine import ContextEngine
from app.ai.models import AIError, AIRequest, AIResult, ImageReference
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers import MockProvider
from app.config import AI_PROVIDER

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, provider: AIProvider | None = None, prompt_builder: PromptBuilder | None = None, context_engine: ContextEngine | None = None):
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.context_engine = context_engine or ContextEngine()
        self.provider = provider or self._build_provider()

    def generate_narration(self, coverage_id: str, photo_id: str, coverage: dict, photo: dict, photo_sequence: int = 0, simulate_error: bool = False) -> AIResult:
        started_at = time.perf_counter()
        provider_name = getattr(self.provider, "provider_name", "unknown")

        try:
            request = self._build_request(coverage_id, photo_id, coverage, photo, photo_sequence, simulate_error)
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
        provider_name = AI_PROVIDER
        if provider_name == "mock":
            return MockProvider()
        raise AIError(
            code="AI_PROVIDER_NOT_CONFIGURED",
            message="El proveedor de IA configurado no está disponible.",
            status_code=503,
            provider=provider_name,
        )

    def build_context_preview(self, coverage_id: str, photo_id: str, coverage: dict, photo: dict, photo_sequence: int = 0) -> dict:
        context = self.context_engine.build(coverage_id, coverage, photo, photo_sequence)
        return self.context_engine.to_json_payload(context)

    def _build_request(self, coverage_id: str, photo_id: str, coverage: dict, photo: dict, photo_sequence: int, simulate_error: bool) -> AIRequest:
        image = ImageReference(
            photo_id=photo_id,
            filename=str(photo.get("name", "")),
            mime_type=str(photo.get("type", "image/jpeg")),
            size=photo.get("size"),
            width=photo.get("width"),
            height=photo.get("height"),
            data_url=photo.get("data_url"),
        )
        context = self.context_engine.build(coverage_id, coverage, photo, photo_sequence)
        return AIRequest(
            image=image,
            coverage_context=context,
            editorial_instructions=self.prompt_builder.build_editorial_instructions(context),
            language=context.language,
            max_words=60,
            template=context.editorial_template,
            simulate_error=simulate_error,
        )
