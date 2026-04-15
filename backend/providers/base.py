from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat_stream(
        self, messages: list, system: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat response token by token."""
        ...

    @abstractmethod
    async def complete(self, messages: list, system: str = None, **kwargs) -> str:
        """Single-shot completion, returns full text. Used for structured tasks."""
        ...
