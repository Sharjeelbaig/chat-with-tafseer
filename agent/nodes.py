# agent/nodes.py
from time import sleep

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from services.ollama_service import llm
from services.quran_service import Quran

from .state import AgentState

CONTEXT_CHAR_LIMIT = 8000
RECENT_TURN_LIMIT = 6
RECENT_MESSAGE_LIMIT = RECENT_TURN_LIMIT * 2
RECENT_CONVERSATION_CHAR_LIMIT = 1000
CONVERSATION_SNIPPET_CHAR_LIMIT = 80
MODEL_RETRY_DELAYS_SECONDS = (0.25, 0.75)
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
    messages = state["messages"]
    if not messages:
        return []

    latest_message = messages[-1]
    if not isinstance(latest_message, HumanMessage):
        return messages[-RECENT_MESSAGE_LIMIT:]

    recent_history = messages[:-1][-RECENT_MESSAGE_LIMIT:]
    return [*recent_history, latest_message]


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


def _is_retryable_model_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    message = str(error).lower()
    retryable_markers = (
        "bad gateway",
        "gateway",
        "temporarily unavailable",
        "rate limit",
        "too many requests",
        "connection reset",
        "timed out",
        "timeout",
        "overloaded",
    )
    return any(marker in message for marker in retryable_markers)


def invoke_llm(messages: list[BaseMessage]):
    for attempt, delay_seconds in enumerate((0.0, *MODEL_RETRY_DELAYS_SECONDS), start=1):
        if delay_seconds > 0:
            sleep(delay_seconds)

        try:
            return llm.invoke(messages)
        except Exception as error:
            if attempt == len(MODEL_RETRY_DELAYS_SECONDS) + 1:
                raise
            if not _is_retryable_model_error(error):
                raise


def _format_recent_conversation(messages: list[BaseMessage]) -> str:
    if not messages:
        return "No prior conversation."

    lines = []
    for message in messages:
        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        else:
            continue
        content = " ".join(str(message.content).split())
        if len(content) > CONVERSATION_SNIPPET_CHAR_LIMIT:
            content = content[: CONVERSATION_SNIPPET_CHAR_LIMIT - 3].rstrip() + "..."
        lines.append(f"{role}: {content}")

    if not lines:
        return "No prior conversation."

    kept_lines = []
    total_length = 0
    for line in reversed(lines):
        added_length = len(line) + (1 if kept_lines else 0)
        if total_length + added_length > RECENT_CONVERSATION_CHAR_LIMIT:
            break
        kept_lines.append(line)
        total_length += added_length

    return "\n".join(reversed(kept_lines))


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
    recent_conversation = _format_recent_conversation(_recent_messages(state)[:-1])
    current_question = state["messages"][-1].content

    system = f"""You are a knowledgeable Islamic tafseer assistant.

Answer the user's question using only the tafseer context provided below for verse {verse_key} from chapter {chapter}.
Use the recent conversation to resolve follow-up references such as "that", "this", "summarize it", or "my previous question".
If the user refers back to an earlier exchange, anchor your answer to that exchange while staying within the tafseer context.
If the answer is not clearly supported by the provided tafseer context, say so directly.
Do not invent facts or cite verses beyond the provided context unless the context itself mentions them.
Keep the answer concise, grounded, respectful, and preferably under 120 words.

RECENT CONVERSATION:
{recent_conversation}

TAFSEER CONTEXT:
{tafseer[:CONTEXT_CHAR_LIMIT]}
"""

    try:
        response = invoke_llm([SystemMessage(content=system), HumanMessage(content=current_question)])
    except Exception as error:
        raise _classify_model_error(error) from error

    content = getattr(response, "content", "")
    if not isinstance(content, str) or not content.strip():
        raise ModelServiceError("Ollama returned an empty chat response", 502)

    return {"messages": [AIMessage(content=content.strip())]}
