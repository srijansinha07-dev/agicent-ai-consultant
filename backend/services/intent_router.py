from __future__ import annotations

from typing import Literal

from config import GROQ_API_KEY, GROQ_MODEL, USE_GROQ

IntentLabel = Literal[
    "greeting",
    "acknowledgement",
    "follow_up",
    "consultant_question",
    "project_inquiry",
    "lead_intent",
]

_VALID_INTENTS: tuple[IntentLabel, ...] = (
    "greeting",
    "acknowledgement",
    "follow_up",
    "consultant_question",
    "project_inquiry",
    "lead_intent",
)


def classify_intent(query: str, history: list[dict] | None = None) -> IntentLabel:
    """
    Lightweight intent classifier that decides routing before retrieval.
    LLM-first for generalization, tiny heuristic fallback for resilience.
    """
    q = (query or "").strip()
    if not q:
        return "acknowledgement"

    if USE_GROQ and GROQ_API_KEY:
        predicted = _classify_with_llm(q, history or [])
        if predicted in _VALID_INTENTS:
            return predicted

    return _fallback_intent(q)


def route_without_retrieval(intent: IntentLabel) -> bool:
    return intent in {"greeting", "acknowledgement", "follow_up"}


def generate_conversational_reply(
    *,
    intent: IntentLabel,
    query: str,
    history: list[dict] | None = None,
) -> str:
    """
    Response for non-retrieval paths only.
    """
    h = history or []
    if intent == "greeting":
        return (
            "Hi! Happy to help. Share what you're building or deciding, "
            "and I can help you think through options."
        )
    if intent == "acknowledgement":
        return "Makes sense. If you want, I can help you go one level deeper on the next step."

    # follow_up: use conversation context, but still avoid retrieval pipeline.
    if USE_GROQ and GROQ_API_KEY:
        reply = _follow_up_with_llm(query, h)
        if reply:
            return reply

    # deterministic fallback using last assistant message
    last_assistant = _last_message_by_role(h, "assistant")
    if last_assistant:
        return (
            f"Good question. I meant this in practical terms: {last_assistant[:220].strip()} "
            "If you want, I can break down one specific part."
        )
    return "Good question. I can clarify that further if you tell me which part you want unpacked."


def _classify_with_llm(query: str, history: list[dict]) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    history_tail = history[-6:]
    prompt = (
        "Classify the latest user message intent.\n"
        "Return ONE label only from:\n"
        "- greeting\n"
        "- acknowledgement\n"
        "- follow_up\n"
        "- consultant_question\n"
        "- project_inquiry\n"
        "- lead_intent\n\n"
        "Guidelines:\n"
        "- greeting: social openers (hi/hello etc)\n"
        "- acknowledgement: short reactions (thanks/ok/makes sense/hmm/cool/etc)\n"
        "- follow_up: clarifying reactions to prior answer (why/what do you mean/explain that)\n"
        "- consultant_question: substantive product/tech/team/cost strategy question\n"
        "- project_inquiry: concrete product planning or implementation discussion\n"
        "- lead_intent: explicit hiring/team/budget/engagement interest\n\n"
        f"Conversation tail: {history_tail}\n"
        f"Latest user message: {query}\n\n"
        "Label:"
    )
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=8,
    )
    return (resp.choices[0].message.content or "").strip().lower()


def _follow_up_with_llm(query: str, history: list[dict]) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    history_tail = history[-8:]
    prompt = (
        "You are in a chat. The user asked a follow-up clarification.\n"
        "Respond naturally in 1-3 concise sentences.\n"
        "- Use the conversation history only.\n"
        "- Do not use retrieval/source mentions.\n"
        "- Keep tone conversational and helpful.\n\n"
        f"Conversation: {history_tail}\n"
        f"User follow-up: {query}\n\n"
        "Assistant reply:"
    )
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=120,
    )
    return (resp.choices[0].message.content or "").strip()


def _fallback_intent(query: str) -> IntentLabel:
    q = query.strip().lower()
    token_count = len([t for t in q.split() if t])
    if token_count <= 2 and q in {"hi", "hello", "hey", "yo"}:
        return "greeting"
    if token_count <= 3 and q in {"thanks", "thank you", "ok", "okay", "alright", "hmm", "cool"}:
        return "acknowledgement"
    if "?" in q and token_count <= 6:
        return "follow_up"
    return "consultant_question"


def _last_message_by_role(history: list[dict], role: str) -> str | None:
    for item in reversed(history):
        if (item.get("role") or "").lower() == role:
            content = (item.get("content") or "").strip()
            if content:
                return content
    return None

