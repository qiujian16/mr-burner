import asyncio
import json
import uuid
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from agent import LayoffLawyerAgent
from memory import ConsultationMemory
from memory_palace import MemPalaceStore
from providers import get_provider, DEFAULT_PROVIDER

app = FastAPI(title="N+1 收割机")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = ConsultationMemory("./data")
palace = MemPalaceStore("../palace")


def make_agent(provider_name: str) -> LayoffLawyerAgent:
    return LayoffLawyerAgent(get_provider(provider_name))


# ── Request models ────────────────────────────────────────────────────────────

class NewSessionRequest(BaseModel):
    provider: str = DEFAULT_PROVIDER


class ChatRequest(BaseModel):
    message: str
    provider: str = DEFAULT_PROVIDER


# ── SSE helper ────────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/sessions/new")
async def new_session(req: NewSessionRequest):
    session_id = str(uuid.uuid4())[:8]
    session = memory.create_session(session_id, provider=req.provider)
    return {"session_id": session_id, "session": session}


@app.get("/api/sessions")
async def list_sessions():
    return memory.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = memory.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if not memory.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, req: ChatRequest):
    session = memory.load_session(session_id)
    if not session:
        session = memory.create_session(session_id, provider=req.provider)

    user_message = req.message
    provider_name = req.provider or session.get("provider", DEFAULT_PROVIDER)
    agent = make_agent(provider_name)

    # Build message history (API format, no timestamps)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in session["messages"]
    ]
    history.append({"role": "user", "content": user_message})

    # Search palace for relevant past cases before streaming
    context = palace.search_context(user_message)

    async def generate():
        full_response = ""
        try:
            async for chunk in agent.chat_stream(history, context=context):
                full_response += chunk
                yield sse({"type": "text", "content": chunk})

            # Persist messages
            memory.add_message(session_id, "user", user_message)
            memory.add_message(session_id, "assistant", full_response)

            # Extract structured info from recent conversation
            updated = memory.load_session(session_id)
            recent_msgs = updated["messages"][-14:]
            conversation_text = "\n".join(
                f"{'用户' if m['role'] == 'user' else '小惠'}: {m['content']}"
                for m in recent_msgs
            )
            extracted = await agent.extract_info(conversation_text)
            if extracted:
                if extracted.get("employee_info"):
                    memory.update_employee_info(session_id, extracted["employee_info"])
                if extracted.get("company_offer"):
                    memory.update_company_offer(session_id, extracted["company_offer"])
                if extracted.get("case_summary"):
                    memory.update_case_summary(session_id, extracted["case_summary"])

            final_session = memory.load_session(session_id)

            # Mine updated session into palace for future semantic search
            palace.mine_session(session_id, final_session)

            yield sse({"type": "done", "session": final_session})

        except Exception as e:
            yield sse({"type": "error", "content": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/sessions/{session_id}/analyze")
async def analyze(session_id: str, req: NewSessionRequest):
    session = memory.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    provider_name = req.provider or session.get("provider", DEFAULT_PROVIDER)
    agent = make_agent(provider_name)

    async def generate():
        full_analysis = ""
        try:
            async for chunk in agent.generate_analysis(session):
                full_analysis += chunk
                yield sse({"type": "text", "content": chunk})

            memory.update_analysis(session_id, full_analysis)
            final_session = memory.load_session(session_id)
            palace.mine_session(session_id, final_session)
            yield sse({"type": "done", "session": final_session})

        except Exception as e:
            yield sse({"type": "error", "content": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/providers")
async def list_providers():
    """Return which providers are configured (have API keys)."""
    available = []
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append({"id": "claude", "name": "Claude (Anthropic)"})
    if os.getenv("MINIMAX_API_KEY"):
        available.append({"id": "minimax", "name": "MiniMax"})
    if os.getenv("DASHSCOPE_API_KEY"):
        available.append({"id": "qwen", "name": "Qwen (通义千问)"})
    return available


# ── Static frontend ───────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
