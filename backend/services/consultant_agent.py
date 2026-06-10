"""
services/consultant_agent.py
─────────────────────────────
Primary entry point for the Agicent consultant agent on website-doc queries.

Architecture per turn:
    1. Load / create ConversationState (in-memory, TTL-evicted)
    2. Extract project signals from user message → update state + lead score
    3. Run DecisionEngine → choose action (zero LLM tokens)
    4. Branch:
       - REDIRECT / DISCOVERY / OFFER / BOOK → deterministic response (0 tokens)
       - RETRIEVE_AND_ANSWER / PROVIDE_RECOMMENDATION
           → build compressed prompt (rolling summary + last 3 msgs)
           → retrieve only when needed
           → single Groq call
           → update rolling summary every 3 turns
    5. Log token analytics
    6. Return result in the same dict format as langgraph_chat.run_chat_graph()
       so the chat.py router needs no schema changes.

Backward compatibility:
    - Non-website docs NEVER reach this module.
    - If CONSULTANT_AGENT_ENABLED=false, chat.py bypasses this entirely.
    - The ChromaDB / retriever stack is reused unchanged.
    - The ChatResponse API contract is unchanged.
"""
from __future__ import annotations

import re
from typing import Any

from config import GROQ_API_KEY, GROQ_MODEL, USE_GROQ
from models import QueryType
from services import conversation_state as cs_store
from services.conversation_state import ConversationState
from services.decision_engine import AgentAction, decide
from services.token_analytics import estimate_tokens, log_request
from services.website_support import (
    CONSULTANT_PROMPT_COMPRESSED,
    DISCOVERY_QUESTIONS,
    DOMAIN_REDIRECT_MESSAGE,
    get_consultation_offer_message,
)


# ── Config ─────────────────────────────────────────────────────────────────
_MAX_HISTORY_MSGS   = 3        # last N messages included in prompt
_SUMMARY_EVERY_N    = 3        # update rolling summary every N assistant turns
_CONTEXT_CHAR_LIMIT = 2000     # chars of retrieved context sent to LLM
_ANSWER_MAX_TOKENS  = 300


# ── Public API ──────────────────────────────────────────────────────────────

def run_consultant_agent(
    *,
    session_id: str,
    query: str,
    history: list[dict],
    doc_id: str,
    chunks_all: list,
    pages_all: list,
    doc_info: Any,
) -> dict:
    """
    Main entry point. Returns the same dict as run_chat_graph():
        {"answer": str, "query_type": QueryType, "retrieved_chunks": list, "doc_info": Any}
    """
    # 1. Load / create state
    state = cs_store.get_or_create(session_id)

    # 2. Extract signals from user message → update lead score
    state.update_from_message(query)
    cs_store.update(session_id, state)

    # 3. Decide action
    action = decide(query, state)

    print(f"[ConsultantAgent] session={session_id[:12]} action={action} "
          f"lead_score={state.lead_score} turn={state.turn_count}")

    # ── Fast paths (zero LLM tokens) ──────────────────────────────────────
    if action == AgentAction.REDIRECT_TO_DOMAIN:
        return _zero_token_response(DOMAIN_REDIRECT_MESSAGE, doc_info,
                                    session_id, action, state=state)

    if action == AgentAction.ASK_DISCOVERY_QUESTION:
        return _handle_discovery(state, session_id, query, history, doc_info, action)

    if action == AgentAction.OFFER_CONSULTATION:
        state.consultation_offered = True
        state.booking_status = "offered"
        cs_store.update(session_id, state)
        summary_parts = []
        if getattr(state, "industry", None):
            summary_parts.append(f"Industry: {state.industry}")
        if getattr(state, "project_type", None):
            summary_parts.append(f"Project Type: {state.project_type}")
        if getattr(state, "budget", None):
            summary_parts.append(f"Budget: {state.budget}")
        summary_parts.append("Interested in discussing scope, timeline, architecture, and delivery approach with Agicent.")

        consultation_summary = "\n".join(summary_parts)

        msg = get_consultation_offer_message(state)

        return _pack(answer=msg,retrieved_chunks=[],doc_info=doc_info,action=action,consultation_summary=consultation_summary,budget=state.budget,timeline=state.timeline)

    if action == AgentAction.BOOK_CALL:
        return _handle_book_call(state, session_id, doc_info, action)

    # ── Retrieval paths ────────────────────────────────────────────────────
    if action == AgentAction.PROVIDE_RECOMMENDATION:
        return _handle_recommendation(
            state=state, session_id=session_id, query=query,
            history=history, doc_id=doc_id, chunks_all=chunks_all,
            pages_all=pages_all, doc_info=doc_info, action=action,
        )

    # Default: RETRIEVE_AND_ANSWER
    return _handle_retrieve_and_answer(
        state=state, session_id=session_id, query=query,
        history=history, doc_id=doc_id, chunks_all=chunks_all,
        pages_all=pages_all, doc_info=doc_info, action=action,
    )


# ── Action handlers ─────────────────────────────────────────────────────────

def _handle_discovery(
    state: ConversationState,
    session_id: str,
    query: str,
    history: list[dict],
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    Return next discovery question OR a brief follow-up reply for greetings/acks.
    Zero LLM tokens when we have a deterministic question template.
    Falls back to a light LLM call only for follow-up clarifications.
    """
    q_lower = query.strip().lower()

    # Pure greeting → warm welcome + first question
    _greeting_re = re.compile(
        r"^(hi+|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|yo|sup)[!.,?]*$",
        re.IGNORECASE,
    )
    if _greeting_re.match(query.strip()):
        first_q = DISCOVERY_QUESTIONS.get("industry", "What are you building?")
        msg = (
            "Hi! I'm your Agicent AI Consultant — here to help you think through "
            "your project, AI strategy, or team model from Agicent's perspective.\n\n"
            f"{first_q}"
        )
        state.mark_asked("industry")
        cs_store.update(session_id, state)
        return _zero_token_response(msg, doc_info, session_id, action, state=state)

    # Ack → brief and pivot
    _ack_re = re.compile(
        r"^(thanks?|thank\s+you|ok(?:ay)?|got\s+it|understood|makes?\s+sense"
        r"|sounds?\s+good|cool|great|nice|perfect|alright|sure|yep|yup)[!.,?]*$",
        re.IGNORECASE,
    )
    if _ack_re.match(query.strip()):
        next_field = state.next_discovery_field()
        if next_field:
            q_text = DISCOVERY_QUESTIONS[next_field]
            state.mark_asked(next_field)
            cs_store.update(session_id, state)
            msg = f"Got it. {q_text}"
            return _zero_token_response(msg, doc_info, session_id, action, state=state)
        return _zero_token_response(
            "Got it. What would you like to dig into next?",
            doc_info, session_id, action, state=state
        )

    # Missing field → ask next discovery question
    next_field = state.next_discovery_field()
    if next_field:
        q_text = DISCOVERY_QUESTIONS[next_field]
        state.mark_asked(next_field)
        cs_store.update(session_id, state)

        # For first turn with real content, prefix with context acknowledgement
        if state.turn_count == 1:
            msg = f"Interesting. {q_text}"
        else:
            msg = q_text
        return _zero_token_response(msg, doc_info, session_id, action, state=state)

    # All fields known — pivot to retrieval
    return _handle_retrieve_and_answer(
        state=state, session_id=session_id, query=query,
        history=history, doc_id="agicent_website", chunks_all=[],
        pages_all=[], doc_info=doc_info, action=AgentAction.RETRIEVE_AND_ANSWER,
    )


def _handle_book_call(
    state: ConversationState,
    session_id: str,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    Handle BOOK_CALL action — check calendar availability and present booking options.
    Gracefully falls back to consultation form if calendar is not configured.
    """
    state.booking_status = "collecting"
    cs_store.update(session_id, state)

    # Try Google Calendar if configured
    try:
        from services.calendar_service import GoogleCalendarService, CalendarNotConfiguredError
        cal = GoogleCalendarService()
        slots = cal.get_available_slots(days_ahead=7)

        if slots:
            print(f"[ConsultantAgent] BOOKING SLOTS: {len(slots)} slots across multiple days")
            return _zero_token_response(
                "Select a discovery call slot below.",
                doc_info, session_id, action,
                state=state,
                available_slots=slots,
            )

    except Exception as e:
        print(f"[ConsultantAgent] Calendar unavailable: {e}")

    # Fallback: direct to consultation form
    msg = (
        "I'd love to get a discovery call on the calendar. "
        "To set that up, please fill in the consultation form — "
        "click **[Request Consultation]** below and share your name, email, "
        "project description, and preferred timeline. "
        "The Agicent team will follow up within one business day."
    )
    return _zero_token_response(msg, doc_info, session_id, action, state=state)


def _handle_recommendation(
    *,
    state: ConversationState,
    session_id: str,
    query: str,
    history: list[dict],
    doc_id: str,
    chunks_all: list,
    pages_all: list,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    Give an Agicent-specific recommendation using state context + limited retrieval.
    Uses a condensed prompt with state snippet instead of full history.
    """
    # Try retrieval for Agicent-specific context
    retrieved_chunks, context_text = _retrieve(doc_id, query, chunks_all, pages_all)

    # Build compressed prompt
    state_snippet = state.to_context_snippet()
    recent_msgs   = _format_recent_history(history, n=_MAX_HISTORY_MSGS)
    summary_block = f"Conversation so far: {state.conversation_summary}\n" if state.conversation_summary else ""

    prompt = (
        f"{CONSULTANT_PROMPT_COMPRESSED}\n\n"
        f"{summary_block}"
        f"Known context: {state_snippet}\n\n"
        + (f"CONTEXT:\n{context_text}\n\n" if context_text else "")
        + f"{recent_msgs}"
        f"USER: {query}\n\n"
        "CONSULTANT RESPONSE (focus on how Agicent would approach this project):"
    )

    answer = _groq(prompt, max_tokens=_ANSWER_MAX_TOKENS)

    # Update rolling summary
    _maybe_update_summary(state, session_id, query, answer)

    log_request(
        session_id=session_id, action=action.value, prompt=prompt, answer=answer,
        retrieval_used=bool(retrieved_chunks), chunk_count=len(retrieved_chunks),
        context_chars=len(context_text),
    )
    return _pack(answer,retrieved_chunks,doc_info,action=action,budget=state.budget,timeline=state.timeline)


def _handle_retrieve_and_answer(
    *,
    state: ConversationState,
    session_id: str,
    query: str,
    history: list[dict],
    doc_id: str,
    chunks_all: list,
    pages_all: list,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    RAG path with token-optimised prompt.
    Uses rolling summary + last 3 messages instead of full history.
    """
    retrieved_chunks, context_text = _retrieve(doc_id, query, chunks_all, pages_all)

    state_snippet = state.to_context_snippet()
    recent_msgs   = _format_recent_history(history, n=_MAX_HISTORY_MSGS)
    summary_block = f"Conversation so far: {state.conversation_summary}\n" if state.conversation_summary else ""

    prompt = (
        f"{CONSULTANT_PROMPT_COMPRESSED}\n\n"
        f"{summary_block}"
        + (f"Known context: {state_snippet}\n\n" if state_snippet else "")
        + (f"CONTEXT:\n{context_text}\n\n" if context_text else "")
        + f"{recent_msgs}"
        f"USER: {query}\n\n"
        "CONSULTANT RESPONSE:"
    )

    answer = _groq(prompt, max_tokens=_ANSWER_MAX_TOKENS)

    _maybe_update_summary(state, session_id, query, answer)

    log_request(
        session_id=session_id, action=action.value, prompt=prompt, answer=answer,
        retrieval_used=bool(retrieved_chunks), chunk_count=len(retrieved_chunks),
        context_chars=len(context_text),
    )
    return _pack(answer,retrieved_chunks,doc_info,action=action,budget=state.budget,timeline=state.timeline)


# ── Rolling summary ────────────────────────────────────────────────────────

def _maybe_update_summary(
    state: ConversationState,
    session_id: str,
    user_msg: str,
    assistant_msg: str,
) -> None:
    """Update rolling conversation summary every N assistant turns."""
    if state.turn_count % _SUMMARY_EVERY_N != 0:
        return
    try:
        existing = state.conversation_summary or ""
        recent = f"User: {user_msg[:200]}\nAssistant: {assistant_msg[:300]}"
        prompt = (
            "Summarise this consulting conversation in 1-2 sentences for AI memory context. "
            "Include: project type, industry, budget/timeline if mentioned, key decisions.\n\n"
            + (f"Previous summary: {existing}\n" if existing else "")
            + f"Recent exchange:\n{recent}\n\n"
            "Summary:"
        )
        new_summary = _groq(prompt, max_tokens=80)
        if new_summary:
            state.conversation_summary = new_summary
        cs_store.update(session_id, state)
    except Exception as e:
        print(f"[ConsultantAgent] Summary update failed: {e}")


# ── Retrieval helper ────────────────────────────────────────────────────────

def _retrieve(
    doc_id: str,
    query: str,
    chunks_all: list,
    pages_all: list,
) -> tuple[list, str]:
    """Call existing retriever unchanged. Returns (chunks, context_text)."""
    try:
        from services import retriever as ret_svc
        result = ret_svc.retrieve(
            doc_id=doc_id, query=query,
            chunks=chunks_all, pages=pages_all,
        )
        chunks = result.chunks or []
        parts = []
        size  = 0
        for c in chunks:
            block = c.text
            if size + len(block) > _CONTEXT_CHAR_LIMIT:
                break
            parts.append(block)
            size += len(block)
        return chunks, "\n\n".join(parts)
    except Exception as e:
        print(f"[ConsultantAgent] Retrieval error: {e}")
        return [], ""


# ── Groq helper ─────────────────────────────────────────────────────────────

def _groq(prompt: str, max_tokens: int = _ANSWER_MAX_TOKENS) -> str:
    """Single Groq call. Returns empty string on failure."""
    if not USE_GROQ or not GROQ_API_KEY:
        return "Groq is not configured. Please set USE_GROQ=true and GROQ_API_KEY."
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[ConsultantAgent] Groq error: {e}")
        return f"I'm having trouble generating a response right now. Please try again. ({e})"


# ── Prompt helpers ──────────────────────────────────────────────────────────

def _format_recent_history(history: list[dict], n: int = 3) -> str:
    """Format the last N message pairs as a compact dialogue block."""
    if not history:
        return ""
    tail = history[-(n * 2):]  # up to N user+assistant pairs
    lines = []
    for msg in tail:
        role = (msg.get("role") or "user").upper()
        content = (msg.get("content") or "").strip()[:300]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n" if lines else ""


# ── Response helpers ─────────────────────────────────────────────────────────

def _zero_token_response(
    message: str,
    doc_info: Any,
    session_id: str,
    action: AgentAction,
    state: ConversationState | None = None,
    available_slots=None,
) -> dict:
    """Return a deterministic response without any LLM call."""
    log_request(
        session_id=session_id, action=action.value,
        prompt="", answer=message,
        retrieval_used=False, chunk_count=0, context_chars=0,
    )
    budget = state.budget if state else None
    timeline = state.timeline if state else None
    return _pack(message, [], doc_info, action=action, available_slots=available_slots, budget=budget, timeline=timeline)

def _pack(
    answer: str,
    retrieved_chunks: list,
    doc_info: Any,
    action=None,
    consultation_summary: str | None = None,
    available_slots=None,
    budget: str | None = None,
    timeline: str | None = None,
) -> dict:
    return {
        "answer": answer,
        "query_type": QueryType.CONCEPT,
        "retrieved_chunks": retrieved_chunks or [],
        "doc_info": doc_info,
        "action": action,
        "consultationSummary": consultation_summary,
        "availableSlots": available_slots,
        "budget": budget,
        "timeline": timeline,
    }