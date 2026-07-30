from abc import ABC, abstractmethod

from app.ai.models import AIRequest, AIResult


class AIProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def generate_narration(self, request: AIRequest) -> AIResult:
        """Generate only the editable editorial narration for one photo."""
