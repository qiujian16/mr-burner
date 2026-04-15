from .base import LLMProvider
from .claude import ClaudeProvider
from .openai_compat import OpenAICompatProvider
import os


def get_provider(name: str) -> LLMProvider:
    name = name.lower()
    if name == "claude":
        return ClaudeProvider()
    elif name == "minimax":
        return OpenAICompatProvider(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.chat/v1",
            model=os.getenv("MINIMAX_MODEL", "MiniMax-Text-01"),
            fast_model=os.getenv("MINIMAX_FAST_MODEL", "MiniMax-Text-01"),
            provider_name="minimax",
        )
    elif name == "qwen":
        return OpenAICompatProvider(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=os.getenv("QWEN_MODEL", "qwen-max"),
            fast_model=os.getenv("QWEN_FAST_MODEL", "qwen-turbo"),
            provider_name="qwen",
        )
    else:
        raise ValueError(f"Unknown provider: {name}")


DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "claude")
