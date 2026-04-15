from openai import AsyncOpenAI
from typing import AsyncGenerator
from .base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    """
    Covers any provider with an OpenAI-compatible chat completion API,
    e.g. MiniMax (https://api.minimax.chat/v1) and
         Qwen/DashScope (https://dashscope.aliyuncs.com/compatible-mode/v1).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        fast_model: str,
        provider_name: str = "openai_compat",
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.fast_model = fast_model
        self.provider_name = provider_name

    async def chat_stream(
        self, messages: list, system: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        full_messages = [{"role": "system", "content": system}] + messages
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            stream=True,
            max_tokens=4096,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def complete(self, messages: list, system: str = None, **kwargs) -> str:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages += messages
        resp = await self.client.chat.completions.create(
            model=self.fast_model,
            messages=full_messages,
            max_tokens=2048,
        )
        return resp.choices[0].message.content
