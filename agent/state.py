# agent/state.py
from typing import TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: list[BaseMessage]
    resource_id: int | None
    verse_key: str | None
    chapter_number: int | None
    tafseer_text: str | None
