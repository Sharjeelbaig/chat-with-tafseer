# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from requests import HTTPError, RequestException
from langchain_core.messages import HumanMessage

from services.quran_service import Quran
from agent.graph import tafseer_agent

app = FastAPI(title="Chat with Tafseer")
quran = Quran()


# ── Request/Response models ────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"   # one thread_id per conversation session


class ChatResponse(BaseModel):
    answer: str
    chapter_number: int | None


# ── Original tafseer endpoint (keep it) ───────────────────────────
@app.get("/tafseer/{resource_id}/chapter/{chapter_number}")
def get_tafseer(resource_id: int, chapter_number: int):
    try:
        return quran.get_tafseer_by_chapter(resource_id, chapter_number)
    except HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except RequestException as e:
        raise HTTPException(status_code=502, detail="Failed to reach Quran API")


# ── New: Chat endpoint ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Multi-turn chat with Quran tafseer.

    The thread_id is the key to conversation memory:
    - Same thread_id = LangGraph loads previous state (chapter, tafseer, history)
    - New thread_id  = fresh conversation
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    # We only pass the NEW message — LangGraph's checkpointer automatically
    # merges it with the stored history for this thread_id
    result = tafseer_agent.invoke(
        {"messages": [HumanMessage(content=req.message)]},
        config=config,
    )

    last_message = result["messages"][-1]
    return ChatResponse(
        answer=last_message.content,
        chapter_number=result.get("chapter_number"),
    )
