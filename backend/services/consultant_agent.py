"""
services/consultant_agent.py
─────────────────────────────
Primary entry point for the Agicent consultant agent on website-doc queries.

Architecture per turn:
    1. Load / create ConversationState (in-memory, TTL-evicted)
    2. Extract project signals from user message → update state + lead score
    3. Classify user intent (intent_classifier.Intent)
    4. Route to action (decision_engine.AgentAction) via intent-first routing
    5. Branch:
       - REDIRECT / CONFUSION / DISCOVERY / OFFER / BOOK → deterministic (0 tokens)
       - RETRIEVE_AND_ANSWER / PROVIDE_RECOMMENDATION
           → build intent-aware prompt (rolling summary + last 3 msgs)
           → retrieve only when needed
           → single Groq call
           → update rolling summary every 3 turns
    6. Log token analytics
    7. Return result in the same dict format as langgraph_chat.run_chat_graph()

Identity:
    The assistant is Agicent's AI Consultant — NOT a human consultant.
    It never claims personal experience, personal recommendations, or human identity.

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
from services.intent_classifier import Intent, classify
from services.token_analytics import estimate_tokens, log_request
from services.website_support import (
    CONSULTANT_PROMPT_COMPRESSED,
    DISCOVERY_QUESTIONS,
    DISCOVERY_QUESTION_VARIANTS,
    DOMAIN_REDIRECT_MESSAGE,
    get_consultation_offer_message,
)


# ── Config ─────────────────────────────────────────────────────────────────
_MAX_HISTORY_MSGS    = 1        # last 1 turn-pair (user+assistant) in every prompt
_SUMMARY_EVERY_N     = 3        # update rolling summary every N assistant turns
_CONTEXT_CHAR_LIMIT  = 800      # chars of retrieved context for standard queries (~200 tokens)
_CONTEXT_CHAR_LIMIT_RICH = 1600 # chars for case studies / detailed process queries (~400 tokens)
_ANSWER_MAX_TOKENS   = 250
_MAX_CHUNKS_STANDARD = 1        # retrieval budget: 1 chunk for normal knowledge queries
_MAX_CHUNKS_RICH     = 3        # retrieval budget: 3 chunks for case studies / detailed process


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
    booking_state: Optional[dict] = None,
) -> dict:
    """
    Main entry point. Returns the same dict as run_chat_graph():
        {"answer": str, "query_type": QueryType, "retrieved_chunks": list, "doc_info": Any}
    """
    # 1. Load / create state
    state = cs_store.get_or_create(session_id)
    if booking_state:
        state.active_booking = booking_state

    # 2. Extract signals from user message → update lead score
    state.update_from_message(query)
    cs_store.update(session_id, state)

    # 3. Classify intent
    intent = classify(query, state)

    # 4. Route to action
    action = decide(query, state)

    print(
        f"[ConsultantAgent] session={session_id[:12]} intent={intent.value} "
        f"action={action.value} lead_score={state.lead_score} turn={state.turn_count}"
    )

    # ── Fast paths (zero LLM tokens) ──────────────────────────────────────
    if action == AgentAction.REDIRECT_TO_DOMAIN:
        return _zero_token_response(
            DOMAIN_REDIRECT_MESSAGE, doc_info, session_id, action, state=state
        )

    if action == AgentAction.HANDLE_CONFUSION:
        return _handle_confusion(state, session_id, query, doc_info, action)

    if action == AgentAction.ASK_DISCOVERY_QUESTION:
        return _handle_discovery(
            state, session_id, query, history, doc_info, action, intent
        )

    if action == AgentAction.OFFER_CONSULTATION:
        return _handle_offer_consultation(state, session_id, doc_info, action)

    if action == AgentAction.BOOK_CALL:
        return _handle_book_call(state, session_id, doc_info, action)

    # ── State-only path: booking/consultation status — NO retrieval ──────
    if action == AgentAction.STATE_ONLY_ANSWER:
        return _handle_state_only_answer(
            state=state, session_id=session_id, query=query,
            history=history, doc_info=doc_info, action=action, intent=intent,
        )

    # ── Retrieval paths ────────────────────────────────────────────────────
    if action == AgentAction.PROVIDE_RECOMMENDATION:
        return _handle_recommendation(
            state=state, session_id=session_id, query=query,
            history=history, doc_id=doc_id, chunks_all=chunks_all,
            pages_all=pages_all, doc_info=doc_info, action=action, intent=intent,
        )

    # Default: RETRIEVE_AND_ANSWER
    return _handle_retrieve_and_answer(
        state=state, session_id=session_id, query=query,
        history=history, doc_id=doc_id, chunks_all=chunks_all,
        pages_all=pages_all, doc_info=doc_info, action=action, intent=intent,
    )


# ── Action handlers ─────────────────────────────────────────────────────────

def _handle_confusion(
    state: ConversationState,
    session_id: str,
    query: str,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    User is confused or sent noise. Ask them to clarify what they need.
    Never advance discovery on confusion signals.
    """
    # Check what the last thing we asked was
    last_asked = _last_asked_field(state)
    if last_asked:
        q_text = _get_discovery_question(last_asked, state)
        msg = f"Sorry if that wasn't clear. To continue, {q_text.lower()}"
    else:
        msg = (
            "Happy to help — could you tell me a bit more about what you're looking for? "
            "For example, are you exploring Agicent's services, working on a specific project, "
            "or wanting to book a call with the team?"
        )
    return _zero_token_response(msg, doc_info, session_id, action, state=state)


def _handle_discovery(
    state: ConversationState,
    session_id: str,
    query: str,
    history: list[dict],
    doc_info: Any,
    action: AgentAction,
    intent: Intent,
) -> dict:
    """
    Handle discovery flow with intent-awareness.

    Rules:
    - Greeting: warm welcome, ask first contextual question
    - Acknowledgement: briefly confirm, pivot to next question
    - Project discussion: acknowledge project context, ask next relevant question
    - Discovery answer: validate it was a real answer, advance if so
    - Never ask the same question twice
    - Questions are contextual, not rigid templates
    """
    q_lower = query.strip().lower()

    # ── Greeting ──────────────────────────────────────────────────────────
    if intent == Intent.GREETING:
        # Vary welcome by turn — avoid repeating if user says hi again
        if state.turn_count > 1:
            msg = "What can I help you with?"
        else:
            msg = (
                "Hi — I'm Agicent's AI Consultant. "
                "I can help you explore Agicent's services, think through a project, "
                "or book a discovery call.\n\n"
                "What are you working on?"
            )
        cs_store.update(session_id, state)
        return _zero_token_response(msg, doc_info, session_id, action, state=state)

    # ── Acknowledgement ───────────────────────────────────────────────────
    if intent == Intent.ACKNOWLEDGEMENT:
        next_field = state.next_discovery_field()
        if next_field:
            q_text = _get_discovery_question(next_field, state)
            state.mark_asked(next_field)
            cs_store.update(session_id, state)
            return _zero_token_response(
                f"Got it. {q_text}", doc_info, session_id, action, state=state
            )
        return _zero_token_response(
            "Got it. What would you like to dig into?",
            doc_info, session_id, action, state=state,
        )

    # ── Discovery answer ──────────────────────────────────────────────────
    if intent == Intent.DISCOVERY_ANSWER:
        # Confirmed answer received — advance to next field
        next_field = state.next_discovery_field()
        if next_field:
            q_text = _get_discovery_question(next_field, state)
            state.mark_asked(next_field)
            cs_store.update(session_id, state)
            # Brief acknowledgement before asking next question
            ack = _contextual_ack(query, state)
            return _zero_token_response(
                f"{ack} {q_text}", doc_info, session_id, action, state=state
            )
        # All fields gathered — pivot to recommendation
        return _handle_retrieve_and_answer(
            state=state, session_id=session_id, query=query,
            history=history, doc_id="agicent_website", chunks_all=[],
            pages_all=[], doc_info=doc_info, action=AgentAction.RETRIEVE_AND_ANSWER,
            intent=intent,
        )

    # ── Project discussion ────────────────────────────────────────────────
    if intent == Intent.PROJECT_DISCUSSION:
        next_field = state.next_discovery_field()
        if next_field:
            q_text = _get_discovery_question(next_field, state)
            state.mark_asked(next_field)
            cs_store.update(session_id, state)

            # For first turn with real content — acknowledge and ask
            if state.turn_count == 1:
                # Pick a contextual opener
                opener = _project_opener(query, state)
                return _zero_token_response(
                    f"{opener} {q_text}",
                    doc_info, session_id, action, state=state,
                )
            return _zero_token_response(
                q_text, doc_info, session_id, action, state=state
            )

    # ── Vague / fallback ──────────────────────────────────────────────────
    next_field = state.next_discovery_field()
    if next_field:
        q_text = _get_discovery_question(next_field, state)
        state.mark_asked(next_field)
        cs_store.update(session_id, state)
        if state.turn_count == 1:
            msg = (
                "Happy to help. To point you in the right direction — "
                f"{q_text.lower()}"
            )
        else:
            msg = q_text
        return _zero_token_response(msg, doc_info, session_id, action, state=state)

    # All fields answered → pivot to retrieval
    return _handle_retrieve_and_answer(
        state=state, session_id=session_id, query=query,
        history=history, doc_id="agicent_website", chunks_all=[],
        pages_all=[], doc_info=doc_info, action=AgentAction.RETRIEVE_AND_ANSWER,
        intent=intent,
    )


def _handle_offer_consultation(
    state: ConversationState,
    session_id: str,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """Offer a consultation when lead score threshold is reached."""
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
    summary_parts.append(
        "Interested in discussing scope, timeline, and delivery approach with Agicent."
    )
    consultation_summary = "\n".join(summary_parts)

    msg = get_consultation_offer_message(state)
    return _pack(
        answer=msg,
        retrieved_chunks=[],
        doc_info=doc_info,
        action=action,
        consultation_summary=consultation_summary,
        budget=state.budget,
        timeline=state.timeline,
    )


def _handle_book_call(
    state: ConversationState,
    session_id: str,
    doc_info: Any,
    action: AgentAction,
) -> dict:
    """
    Handle BOOK_CALL — check calendar availability and present booking options.
    Falls back to consultation form if calendar is not configured.
    """
    state.booking_status = "collecting"
    cs_store.update(session_id, state)

    try:
        from services.calendar_service import GoogleCalendarService, CalendarNotConfiguredError
        cal = GoogleCalendarService()
        slots = cal.get_available_slots(days_ahead=7)

        if slots:
            print(f"[ConsultantAgent] BOOKING SLOTS: {len(slots)} slots")
            return _zero_token_response(
                "Select a discovery call slot below.",
                doc_info, session_id, action,
                state=state,
                available_slots=slots,
            )

    except Exception as e:
        print(f"[ConsultantAgent] Calendar unavailable: {e}")

    # Fallback: consultation form
    msg = (
        "To set up a discovery call, please fill in the consultation form — "
        "click **[Request Consultation]** below with your name, email, "
        "and a brief project description. "
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
    intent: Intent,
) -> dict:
    """
    Give an Agicent-specific recommendation using state context + limited retrieval.
    """
    retrieved_chunks, context_text = _retrieve(
        doc_id, query, chunks_all, pages_all, max_chunks=_MAX_CHUNKS_STANDARD
    )
    state_snippet = state.to_context_snippet()
    recent_msgs   = _format_recent_history(history, n=_MAX_HISTORY_MSGS)
    summary_block = f"Conversation so far: {state.conversation_summary}\n" if state.conversation_summary else ""

    prompt = (
        f"{CONSULTANT_PROMPT_COMPRESSED}\n\n"
        f"{summary_block}"
        f"Known project context: {state_snippet}\n\n"
        + (f"Information:\n{context_text}\n\n" if context_text else "")
        + f"{recent_msgs}"
        f"USER: {query}\n\n"
        "AGICENT AI CONSULTANT RESPONSE (explain how we would approach this specific project):"
    )

    answer = _groq(prompt, max_tokens=_ANSWER_MAX_TOKENS)
    _maybe_update_summary(state, session_id, query, answer)
    log_request(
        session_id=session_id, action=action.value, prompt=prompt, answer=answer,
        retrieval_used=bool(retrieved_chunks), chunk_count=len(retrieved_chunks),
        context_chars=len(context_text),
    )
    return _pack(answer, retrieved_chunks, doc_info, action=action,
                 budget=state.budget, timeline=state.timeline)


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
    intent: Intent,
) -> dict:
    """
    Intent-aware RAG path. Retrieval budget is controlled per intent.
    """
    from services.intent_classifier import Intent

    # ── Retrieval budget per intent ────────────────────────────────────────
    _RICH_INTENTS = {Intent.KNOWLEDGE_CASE_STUDY, Intent.KNOWLEDGE_PROCESS}
    max_chunks    = _MAX_CHUNKS_RICH if intent in _RICH_INTENTS else _MAX_CHUNKS_STANDARD
    char_limit    = _CONTEXT_CHAR_LIMIT_RICH if intent in _RICH_INTENTS else _CONTEXT_CHAR_LIMIT

    retrieved_chunks, context_text = _retrieve(
        doc_id, query, chunks_all, pages_all, max_chunks=max_chunks, char_limit=char_limit
    )
    state_snippet = state.to_context_snippet()
    recent_msgs   = _format_recent_history(history, n=_MAX_HISTORY_MSGS)
    summary_block = f"Conversation so far: {state.conversation_summary}\n" if state.conversation_summary else ""

    # Intent-specific instruction
    intent_instruction = _intent_instruction(intent, query)

    prompt = (
        f"{CONSULTANT_PROMPT_COMPRESSED}\n\n"
        f"{summary_block}"
        + (f"Known project context:\n{state_snippet}\n\n" if state_snippet else "")
        + (f"Information:\n{context_text}\n\n" if context_text else "")
        + f"{recent_msgs}"
        f"USER: {query}\n\n"
        f"{intent_instruction}"
    )

    answer = _groq(prompt, max_tokens=_ANSWER_MAX_TOKENS)
    _maybe_update_summary(state, session_id, query, answer)
    log_request(
        session_id=session_id, action=action.value, prompt=prompt, answer=answer,
        retrieval_used=bool(retrieved_chunks), chunk_count=len(retrieved_chunks),
        context_chars=len(context_text),
        extra={
            "system_prompt_chars":      len(CONSULTANT_PROMPT_COMPRESSED),
            "state_chars":              len(state_snippet),
            "history_chars":            len(recent_msgs),
            "retrieval_chars":          len(context_text),
            "intent_instruction_chars": len(intent_instruction),
            "user_message_chars":       len(query),
        },
    )
    return _pack(answer, retrieved_chunks, doc_info, action=action,
                 budget=state.budget, timeline=state.timeline)


# ── State-only handler (booking / consultation status) ────────────────────────

def _handle_state_only_answer(
    *,
    state: ConversationState,
    session_id: str,
    query: str,
    history: list[dict],
    doc_info: Any,
    action: AgentAction,
    intent: Intent,
) -> dict:
    """
    Handles BOOKING_STATUS, BOOKING_MANAGEMENT, and CONSULTATION_STATUS.
    Zero retrieval. Uses only ConversationState + active_booking.
    Target: <200 tokens total.
    """
    from services.intent_classifier import Intent

    state_snippet = state.to_context_snippet()
    recent_msgs   = _format_recent_history(history, n=2)  # only last 2 turns
    intent_instruction = _intent_instruction(intent, query)

    prompt = (
        f"{CONSULTANT_PROMPT_COMPRESSED}\n\n"
        + (f"Known project context: {state_snippet}\n\n" if state_snippet else "")
        + f"{recent_msgs}"
        f"USER: {query}\n\n"
        f"{intent_instruction}"
    )

    answer = _groq(prompt, max_tokens=180)  # hard cap for state-only responses
    log_request(
        session_id=session_id, action=action.value, prompt=prompt, answer=answer,
        retrieval_used=False, chunk_count=0, context_chars=0,
        extra={
            "system_prompt_chars":      len(CONSULTANT_PROMPT_COMPRESSED),
            "state_chars":              len(state_snippet),
            "history_chars":            len(recent_msgs),
            "retrieval_chars":          0,
            "intent_instruction_chars": len(intent_instruction),
            "user_message_chars":       len(query),
        },
    )
    return _pack(answer, [], doc_info, action=action,
                 budget=state.budget, timeline=state.timeline)


# ── Intent-specific prompt instructions ─────────────────────────────────────

def _intent_instruction(intent: Intent, query: str) -> str:
    """Return an instruction suffix tuned to the classified intent."""
    from services.intent_classifier import Intent

    if intent == Intent.KNOWLEDGE_CASE_STUDY:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Describe relevant case studies or project examples based on the provided information. "
            "Be specific about what we built, the industry, and the outcome. "
            "If you don't have a specific example, simply say you don't have one right now but can share similar work):"
        )
    if intent == Intent.KNOWLEDGE_PRICING:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Explain our engagement models and pricing approach based on the provided information. "
            "Do not invent specific numbers. If specific pricing isn't available, explain the factors that typically influence cost):"
        )
    if intent == Intent.KNOWLEDGE_TECHNOLOGY:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Describe our technology capabilities and stack based on the provided information. "
            "Be specific about what technologies, frameworks, and platforms we work with):"
        )
    if intent == Intent.KNOWLEDGE_COMPANY:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Give a concise, factual overview of what Agicent does, "
            "who we serve, and what makes us different based on the provided information. Do not use marketing language):"
        )
    if intent == Intent.KNOWLEDGE_PROCESS:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Describe our development and delivery process based on the provided information. "
            "Be specific about methodology, phases, and how we structure projects):"
        )
    if intent in (Intent.BOOKING_STATUS, Intent.BOOKING_MANAGEMENT):
        return (
            "AGICENT AI CONSULTANT RESPONSE (Review the 'Active Booking' or 'Booking' details from the known project information. "
            "If booking details exist, confirm the exact date, time, and Google Meet link provided. "
            "NEVER generate placeholder text like '[insert date]' or '[insert link]'. "
            "If no booking details are found, politely say you don't see a booking in this chat session and ask them to check their email):"
        )
    if intent == Intent.CONSULTATION_STATUS:
        return (
            "AGICENT AI CONSULTANT RESPONSE (Address the consultation status question directly. "
            "Explain that consultation requests are securely routed to our team and we will reach out "
            "by email within one business day):"
        )
    if intent == Intent.GENERAL_QUESTION:
        return "AGICENT AI CONSULTANT RESPONSE (Answer the question naturally and concisely):"

    return "AGICENT AI CONSULTANT RESPONSE:"


# ── Discovery helpers ─────────────────────────────────────────────────────────

def _get_discovery_question(field: str, state: ConversationState) -> str:
    """
    Return a contextual discovery question for the given field.
    Uses DISCOVERY_QUESTION_VARIANTS when relevant context is available,
    falls back to DISCOVERY_QUESTIONS default.
    """
    variants = DISCOVERY_QUESTION_VARIANTS.get(field, {})
    # Try to match by known industry first
    if state.industry and state.industry in variants:
        return variants[state.industry]
    # Try to match by known project type
    if state.project_type and state.project_type in variants:
        return variants[state.project_type]
    # Fall back to default
    return DISCOVERY_QUESTIONS.get(field, "Could you share more about your project?")


def _last_asked_field(state: ConversationState) -> str | None:
    """Return the last field that was asked, if any."""
    priority = ["industry", "project_type", "target_users", "timeline", "budget", "company_stage"]
    # Fields in asked_fields that are still None in state → last asked
    for f in reversed(priority):
        if f in state.asked_fields and getattr(state, f) is None:
            return f
    return None


def _project_opener(query: str, state: ConversationState) -> str:
    """Generate a brief contextual acknowledgement for a project description."""
    q = query.strip()
    ql = q.lower()

    if state.industry:
        industry_display = state.industry.replace("_", " ").title()
        return f"A {industry_display} project — got it."
    if state.project_type == "mvp":
        return "An MVP build — that's a good starting point."
    if state.project_type == "mobile_app":
        return "A mobile app project — understood."
    if state.project_type == "platform":
        return "A platform build — that makes sense."
    if "healthcare" in ql:
        return "A healthcare project — noted."
    if "startup" in ql or "startup" == state.company_stage:
        return "A startup project — got it."
    if "build" in ql or "create" in ql or "develop" in ql:
        return "Understood —"
    return "Got it —"


def _contextual_ack(query: str, state: ConversationState) -> str:
    """Return a brief, non-repetitive acknowledgement for a discovery answer."""
    ql = query.strip().lower()
    if any(w in ql for w in ("healthcare", "health", "medical", "hospital")):
        return "Healthcare — noted."
    if any(w in ql for w in ("fintech", "finance", "banking", "payment")):
        return "Fintech — understood."
    if any(w in ql for w in ("edtech", "education", "learning")):
        return "EdTech — got it."
    if any(w in ql for w in ("startup", "early stage", "pre-seed", "seed")):
        return "Early-stage — understood."
    if any(w in ql for w in ("mvp", "minimum viable", "prototype")):
        return "MVP — good."
    if any(w in ql for w in ("scale", "scaling", "growth")):
        return "Scaling project — got it."
    if any(w in ql for w in ("enterprise", "large", "corporate")):
        return "Enterprise scale — understood."
    return "Got it."


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
            "Include: project type, industry, budget/timeline if mentioned, key topics discussed.\n\n"
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
    max_chunks: int = _MAX_CHUNKS_STANDARD,
    char_limit: int = _CONTEXT_CHAR_LIMIT,
) -> tuple[list, str]:
    """Call existing retriever with intent-aware chunk budget. Returns (chunks, context_text)."""
    try:
        from services import retriever as ret_svc
        result = ret_svc.retrieve(
            doc_id=doc_id, query=query,
            chunks=chunks_all, pages=pages_all,
        )
        chunks = (result.chunks or [])[:max_chunks]  # hard cap from caller
        parts = []
        size  = 0
        for c in chunks:
            block = c.text
            if size + len(block) > char_limit:
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
            temperature=0.15,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[ConsultantAgent] Groq error: {e}")
        return f"I'm having trouble generating a response right now. Please try again. ({e})"


# ── Prompt helpers ──────────────────────────────────────────────────────────

def _format_recent_history(history: list[dict], n: int = 1) -> str:
    """Format the last N turn-pairs (user+assistant) as a compact dialogue block."""
    if not history:
        return ""
    # Each turn pair = 2 messages; cap at n pairs
    tail = history[-(n * 2):]
    lines = []
    for msg in tail:
        role = (msg.get("role") or "user").upper()
        content = (msg.get("content") or "").strip()[:200]  # hard cap per message
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
    budget   = state.budget if state else None
    timeline = state.timeline if state else None
    return _pack(
        message, [], doc_info, action=action,
        available_slots=available_slots, budget=budget, timeline=timeline,
    )


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
        "answer":            answer,
        "query_type":        QueryType.CONCEPT,
        "retrieved_chunks":  retrieved_chunks or [],
        "doc_info":          doc_info,
        "action":            action,
        "consultationSummary": consultation_summary,
        "availableSlots":    available_slots,
        "budget":            budget,
        "timeline":          timeline,
    }