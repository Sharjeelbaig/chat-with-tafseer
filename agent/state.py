# agent/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    # `add_messages` is a special "reducer" — instead of replacing the list
    # on each update, it APPENDS to it. This preserves conversation history.
    messages: Annotated[list[BaseMessage], add_messages]

    # Which surah (1–114) the user is discussing. Persists across turns.
    chapter_number: int | None

    # The fetched tafseer text. We cache it so we don't re-fetch on follow-ups.
    tafseer_text: str | None

    # Flag: do we need to call the API this turn?
    needs_fetch: bool