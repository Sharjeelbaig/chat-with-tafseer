# agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import AgentState
from .nodes import extract_intent, fetch_tafseer, generate_answer, ask_for_chapter


def route_after_intent(state: AgentState) -> str:
    """
    This is the 'traffic controller'. After extract_intent runs,
    LangGraph calls this function and uses the return string to
    decide which node runs next.
    """
    if not state.get("chapter_number"):
        return "ask_for_chapter"    # couldn't figure out the surah
    if state.get("needs_fetch"):
        return "fetch_tafseer"      # new surah — go fetch it
    return "generate_answer"        # same surah — use cached tafseer


def build_graph():
    # ── 1. Create the graph with our state schema ──────────────────
    graph = StateGraph(AgentState)

    # ── 2. Register all nodes ──────────────────────────────────────
    graph.add_node("extract_intent",  extract_intent)
    graph.add_node("fetch_tafseer",   fetch_tafseer)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("ask_for_chapter", ask_for_chapter)

    # ── 3. Entry point ─────────────────────────────────────────────
    graph.set_entry_point("extract_intent")

    # ── 4. Conditional edge: one node → multiple possible next nodes ──
    graph.add_conditional_edges(
        "extract_intent",       # FROM this node...
        route_after_intent,     # ...call this router function...
        {                       # ...map return values to node names
            "ask_for_chapter": "ask_for_chapter",
            "fetch_tafseer":   "fetch_tafseer",
            "generate_answer": "generate_answer",
        }
    )

    # ── 5. Simple edges: these always go to the same place ─────────
    graph.add_edge("fetch_tafseer",   "generate_answer")  # after fetch → answer
    graph.add_edge("generate_answer", END)
    graph.add_edge("ask_for_chapter", END)

    # ── 6. MemorySaver: persists state between API calls ───────────
    #    Each conversation gets a unique thread_id — the checkpointer
    #    saves/loads state automatically using it.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


tafseer_agent = build_graph()