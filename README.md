# Mr. Burns 合规离职顾问 ⚖️

帮你厘清法定权益，争取应得的每一分离职补偿。AI-powered Chinese labor law consultant for your severance rights.

## Quick start

```bash
# 1. Copy env file and fill in at least one API key
cp .env.example .env

# 2. Start the server (creates venv automatically)
./start.sh
```

Open http://localhost:8000

---

## Provider setup

You need **at least one** provider configured. Add the key(s) to `.env`.

### Claude (Anthropic)

1. Get an API key at https://console.anthropic.com
2. Set in `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
DEFAULT_PROVIDER=claude
```

---

### MiniMax

1. Sign up at https://www.minimaxi.com and go to **API Keys** in the console
2. Set in `.env`:

```env
MINIMAX_API_KEY=eyJhbGciOiJSUzI1NiIsInR5cCI6...
MINIMAX_MODEL=MiniMax-Text-01
MINIMAX_FAST_MODEL=MiniMax-Text-01
DEFAULT_PROVIDER=minimax
```

The base URL (`https://api.minimax.chat/v1`) is hardcoded — no need to set it.

> **Note:** MiniMax API keys are long JWT tokens, not short strings. Copy the full token from the console.

---

### Qwen / 通义千问 (DashScope)

1. Get an API key at https://dashscope.aliyuncs.com
2. Set in `.env`:

```env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
QWEN_MODEL=qwen-max
QWEN_FAST_MODEL=qwen-turbo
DEFAULT_PROVIDER=qwen
```

---

### Using multiple providers

You can configure all three at once. The UI dropdown lets you switch providers per conversation at runtime.

```env
ANTHROPIC_API_KEY=sk-ant-...
MINIMAX_API_KEY=eyJhbGci...
DASHSCOPE_API_KEY=sk-...
DEFAULT_PROVIDER=claude
```

---

## Project layout

```
backend/
  main.py            — FastAPI app, SSE streaming routes
  agent.py           — system prompt, extraction & analysis logic
  memory.py          — per-session JSON storage (data/)
  memory_palace.py   — mempalace semantic search integration
  providers/         — LLM provider abstraction layer
frontend/
  index.html / style.css / app.js
palace/              — mempalace ChromaDB index (auto-created)
data/                — session JSON files (auto-created)
```
