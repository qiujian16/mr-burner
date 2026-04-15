import anthropic
from typing import AsyncGenerator
from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()
        self.model = "claude-opus-4-6"
        self.fast_model = "claude-haiku-4-5"

    async def chat_stream(
        self, messages: list, system: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def complete(self, messages: list, system: str = None, **kwargs) -> str:
        kwargs_clean = {}
        if system:
            kwargs_clean["system"] = system
        resp = await self.client.messages.create(
            model=self.fast_model,
            max_tokens=2048,
            messages=messages,
            **kwargs_clean,
        )
        return resp.content[0].text
