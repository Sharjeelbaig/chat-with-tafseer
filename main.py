# main.py
import re

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, field_validator
from requests import HTTPError, RequestException
from fastapi.middleware.cors import CORSMiddleware

from agent.graph import tafseer_agent
from agent.nodes import ModelServiceError
from services.quran_service import Quran

app = FastAPI(title="Chat with Tafseer")
quran = Quran()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    resource_id: int = Field(gt=0)
    verse_key: str
    message: str = Field(min_length=1)
    thread_id: str = Field(default="default", min_length=1)

    @field_validator("verse_key")
    @classmethod
    def validate_verse_key(cls, value: str) -> str:
        verse_key = value.strip()
        if not re.fullmatch(r"\d{1,3}:\d{1,3}", verse_key):
            raise ValueError("verse_key must be in '<chapter>:<verse>' format")
        return verse_key

    @field_validator("message", "thread_id")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class ChatResponse(BaseModel):
    answer: str
    resource_id: int
    verse_key: str
    chapter_number: int | None


def _get_upstream_error_detail(error: HTTPError) -> str:
    response = error.response
    if response is None:
        return "Upstream Quran API request failed"

    try:
        payload = response.json()
    except ValueError:
        return "Upstream Quran API request failed"

    return payload.get("error") or payload.get("message") or "Upstream Quran API request failed"


@app.get("/tafseer/{resource_id}/chapter/{chapter_number}")
def get_tafseer(resource_id: int, chapter_number: int):
    try:
        return quran.get_tafseer_by_chapter(resource_id, chapter_number)
    except HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        detail = _get_upstream_error_detail(error)
        if status_code == 404:
            raise HTTPException(status_code=404, detail=detail) from error
        raise HTTPException(status_code=502, detail=detail) from error
    except RequestException as error:
        raise HTTPException(status_code=502, detail="Failed to fetch tafseer data from upstream Quran API") from error


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        result = tafseer_agent.invoke(
            {
                "resource_id": req.resource_id,
                "verse_key": req.verse_key,
                "messages": [HumanMessage(content=req.message)],
            },
            config=config,
        )
        last_message = result["messages"][-1]
        return ChatResponse(
            answer=last_message.content,
            resource_id=result["resource_id"],
            verse_key=result["verse_key"],
            chapter_number=result.get("chapter_number"),
        )
    except HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        detail = _get_upstream_error_detail(error)
        if status_code == 404:
            raise HTTPException(status_code=404, detail=detail) from error
        raise HTTPException(status_code=502, detail=detail) from error
    except RequestException as error:
        raise HTTPException(status_code=502, detail="Failed to fetch tafseer data from upstream Quran API") from error
    except ModelServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
