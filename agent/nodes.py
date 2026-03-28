# agent/nodes.py
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from services.ollama_service import llm
from services.quran_service import Quran

from .state import AgentState

CONTEXT_CHAR_LIMIT = 8000
RECENT_MESSAGE_LIMIT = 6
quran_service = Quran()


class ModelServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _extract_chapter_number(verse_key: str) -> int | None:
    try:
        chapter_text, _ = verse_key.split(":", maxsplit=1)
        return int(chapter_text)
    except (AttributeError, ValueError):
        return None


def _recent_messages(state: AgentState) -> list[BaseMessage]:
    return state["messages"][-RECENT_MESSAGE_LIMIT:]


def _classify_model_error(error: Exception) -> ModelServiceError:
    message = str(error).lower()
    if "not found" in message or "pull" in message:
        return ModelServiceError("Configured Ollama model is unavailable", 503)
    if (
        "connection refused" in message
        or "failed to connect" in message
        or "timed out" in message
        or "nodename nor servname provided" in message
    ):
        return ModelServiceError("Failed to reach Ollama model service", 503)
    return ModelServiceError("Failed to generate chat response with Ollama", 502)


def invoke_llm(messages: list[BaseMessage]):
    return llm.invoke(messages)


def load_tafseer_context(resource_id: int, verse_key: str) -> dict:
    data = quran_service.get_tafseer_by_ayah(resource_id, verse_key)
    tafsir = data.get("tafsir", {})
    cleaned_text = quran_service.normalize_tafseer_text(tafsir.get("text", ""))
    resolved_verse_key = next(iter((tafsir.get("verses") or {verse_key: {}}).keys()), verse_key)

    if not cleaned_text:
        raise ValueError("Upstream Quran API returned empty tafseer text")

    return {
        "resource_id": tafsir.get("resource_id", resource_id),
        "verse_key": resolved_verse_key,
        "chapter_number": _extract_chapter_number(resolved_verse_key),
        "tafseer_text": cleaned_text,
    }


def generate_answer(state: AgentState) -> dict:
    tafseer = state.get("tafseer_text", "")
    verse_key = state.get("verse_key", "?")
    chapter = state.get("chapter_number") or "?"

    system = f"""You are a knowledgeable Islamic tafseer assistant.

Answer the user's question using only the tafseer context provided below for verse {verse_key} from chapter {chapter}.
If the answer is not clearly supported by the provided tafseer context, say so directly.
Do not invent facts or cite verses beyond the provided context unless the context itself mentions them.
Keep the answer concise, grounded, and respectful.

TAFSEER CONTEXT:
{tafseer[:CONTEXT_CHAR_LIMIT]}
"""

    try:
        response = invoke_llm([SystemMessage(content=system), *_recent_messages(state)])
    except Exception as error:
        raise _classify_model_error(error) from error

    content = getattr(response, "content", "")
    if not isinstance(content, str) or not content.strip():
        raise ModelServiceError("Ollama returned an empty chat response", 502)

    return {"messages": [AIMessage(content=content.strip())]}
