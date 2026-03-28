# agent/nodes.py
import json
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from services.quran_service import Quran
from services.ollama_service import llm
from .state import AgentState

quran_service = Quran()
RESOURCE_ID = 169  # Ibn Kathir English (popular beginner-friendly tafseer)


def _last_human_message(state: AgentState) -> str:
    """Helper: grab the most recent user message text."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


# ─────────────────────────────────────────────
# NODE 1: Understand what the user is asking
# ─────────────────────────────────────────────
def extract_intent(state: AgentState) -> dict:
    """
    Uses the LLM to extract:
      - Which chapter number the user wants (1–114)
      - Whether it's a NEW chapter (so we need to re-fetch)

    Returns a PARTIAL state update — only the keys we touch.
    LangGraph merges this back into the full state automatically.
    """
    user_msg = _last_human_message(state)
    current_chapter = state.get("chapter_number")

    prompt = f"""You are the intent parser for a Quran tafseer chat app.

User message: "{user_msg}"
Currently loaded Surah number: {current_chapter or "none"}

Return ONLY a JSON object with:
- "chapter_number": integer 1-114 if a surah is mentioned (by name or number), else null
- "needs_new_chapter": true if user wants a DIFFERENT surah than currently loaded

Common surah names: Al-Fatiha=1, Al-Baqarah=2, Al-Imran=3, An-Nisa=4, 
Al-Kahf=18, Ya-Sin=36, Ar-Rahman=55, Al-Waqiah=56, Al-Mulk=67, Al-Ikhlas=112,
Al-Falaq=113, An-Nas=114

Return ONLY JSON. Example: {{"chapter_number": 1, "needs_new_chapter": true}}"""

    response = llm.invoke([HumanMessage(content=prompt)])

    # Safely parse the LLM's JSON — it sometimes wraps it in ```
    try:
        raw = re.sub(r"```(?:json)?|```", "", response.content).strip()
        data = json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        data = {}

    new_chapter = data.get("chapter_number") or current_chapter
    needs_new = data.get("needs_new_chapter", new_chapter != current_chapter)

    return {
        "chapter_number": new_chapter,
        "needs_fetch": bool(needs_new and new_chapter),
    }


# ─────────────────────────────────────────────
# NODE 2: Fetch tafseer from Quran API
# ─────────────────────────────────────────────
def fetch_tafseer(state: AgentState) -> dict:
    """
    Calls your existing Quran service and formats the response into
    clean text that the LLM can reason over.
    """
    chapter = state["chapter_number"]
    print(f"📖 Fetching tafseer for Surah {chapter}...")

    data = quran_service.get_tafseer_by_chapter(RESOURCE_ID, chapter)
    tafsirs = data.get("tafsirs", [])

    def strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text or "").strip()

    # Format as "[1:1] In the name of Allah... (tafseer text)"
    parts = [
        f"[{e['verse_key']}] {strip_html(e.get('text', ''))}"
        for e in tafsirs
        if e.get("text")
    ]

    print(f"✅ Loaded {len(parts)} verses.")
    return {
        "tafseer_text": "\n\n".join(parts),
        "needs_fetch": False,
    }


# ─────────────────────────────────────────────
# NODE 3: Chain-of-Thought reasoning + answer
# ─────────────────────────────────────────────
def generate_answer(state: AgentState) -> dict:
    """
    The heart of the agent. Uses Chain-of-Thought prompting:
    we tell the LLM to reason step-by-step BEFORE answering.
    This significantly improves answer quality.
    """
    tafseer = state.get("tafseer_text", "")
    chapter = state.get("chapter_number", "?")

    system = f"""You are a knowledgeable Islamic scholar assistant specializing in Quranic tafseer.

You have been given the tafseer (Ibn Kathir) of Surah {chapter}. Answer the user's question using it.

TAFSEER:
{tafseer[:7000]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Answer using this Chain-of-Thought structure:

**🤔 Understanding the Question**
(What is the user actually asking? Which verses are relevant?)

**📖 What the Tafseer Says**
(Pull out the most relevant commentary, cite verse keys like 1:2)

**💡 Answer**
(Clear, respectful response grounded in the tafseer above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Be accurate, humble, and note if a question goes beyond the tafseer's scope."""

    response = llm.invoke([
        SystemMessage(content=system),
        *state["messages"],   # full history gives the LLM conversation context
    ])

    return {"messages": [AIMessage(content=response.content)]}


# ─────────────────────────────────────────────
# NODE 4: Fallback — ask user to specify chapter
# ─────────────────────────────────────────────
def ask_for_chapter(state: AgentState) -> dict:
    reply = AIMessage(content=(
        "📖 Which Surah would you like to explore? "
        "You can say the name (e.g. *Al-Fatiha*, *Al-Kahf*) "
        "or number (e.g. *Surah 18*)."
    ))
    return {"messages": [reply]}