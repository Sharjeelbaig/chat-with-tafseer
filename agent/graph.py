from copy import deepcopy
from threading import RLock

from .nodes import generate_answer, load_tafseer_context
from .state import AgentState

SESSION_TURN_LIMIT = 12
SESSION_MESSAGE_LIMIT = SESSION_TURN_LIMIT * 2


def _initial_state() -> AgentState:
    return {
        "messages": [],
        "resource_id": None,
        "verse_key": None,
        "chapter_number": None,
        "tafseer_text": None,
    }


class TafseerAgent:
    def __init__(self):
        self._lock = RLock()
        self._sessions: dict[str, AgentState] = {}

    def reset(self):
        with self._lock:
            self._sessions.clear()

    def invoke(self, payload: dict, config: dict | None = None) -> AgentState:
        configurable = (config or {}).get("configurable", {})
        thread_id = configurable.get("thread_id", "default")
        resource_id = payload["resource_id"]
        verse_key = payload["verse_key"]
        incoming_messages = list(payload.get("messages", []))

        if not incoming_messages:
            raise ValueError("Chat input requires at least one message")

        with self._lock:
            previous_state = deepcopy(self._sessions.get(thread_id, _initial_state()))

        state = self._prepare_state(previous_state, resource_id, verse_key)

        if not state.get("tafseer_text"):
            state.update(load_tafseer_context(resource_id, verse_key))

        state["messages"] = [*state["messages"], *incoming_messages]
        state["messages"] = [*state["messages"], *generate_answer(state)["messages"]]
        state["messages"] = self._prune_messages(state["messages"])

        with self._lock:
            self._sessions[thread_id] = deepcopy(state)

        return deepcopy(state)

    def _prepare_state(self, state: AgentState, resource_id: int, verse_key: str) -> AgentState:
        if state.get("resource_id") == resource_id and state.get("verse_key") == verse_key:
            return state

        return {
            "messages": [],
            "resource_id": resource_id,
            "verse_key": verse_key,
            "chapter_number": None,
            "tafseer_text": None,
        }

    def _prune_messages(self, messages):
        if len(messages) <= SESSION_MESSAGE_LIMIT:
            return messages

        return messages[-SESSION_MESSAGE_LIMIT:]


tafseer_agent = TafseerAgent()
