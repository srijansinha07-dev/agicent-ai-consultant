"""
services/decision_engine.py
────────────────────────────
Deterministic decision layer for the Agicent consultant agent.

Given the current user message and ConversationState, returns one of:
  ASK_DISCOVERY_QUESTION   — gather missing project context
  RETRIEVE_AND_ANSWER      — use RAG pipeline to answer
  PROVIDE_RECOMMENDATION   — give Agicent-specific recommendation from state
  OFFER_CONSULTATION       — lead qualified; invite to book
  BOOK_CALL                — user explicitly wants to book a call
  REDIRECT_TO_DOMAIN       — off-topic; politely redirect

No LLM calls here. Zero extra tokens.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.conversation_state import ConversationState


# ── Action enum ────────────────────────────────────────────────────────────

class AgentAction(str, Enum):
    ASK_DISCOVERY_QUESTION = "ASK_DISCOVERY_QUESTION"
    RETRIEVE_AND_ANSWER    = "RETRIEVE_AND_ANSWER"
    PROVIDE_RECOMMENDATION = "PROVIDE_RECOMMENDATION"
    OFFER_CONSULTATION     = "OFFER_CONSULTATION"
    BOOK_CALL              = "BOOK_CALL"
    REDIRECT_TO_DOMAIN     = "REDIRECT_TO_DOMAIN"


# ── Off-topic guard ────────────────────────────────────────────────────────
# Topics that have nothing to do with software, AI, or business strategy.
_OFF_TOPIC_SIGNALS = frozenset([
    "recipe", "cooking", "weather", "sports", "football", "cricket", "tennis",
    "movie", "music", "song", "celebrity", "politics", "election", "president",
    "stock market", "crypto", "bitcoin", "ethereum", "nft", "meme coin",
    "horoscope", "astrology", "religion", "prayer", "god", "relationship advice",
    "dating", "love poem", "write a poem", "diet", "nutrition", "fitness",
    "homework help", "essay writing", "translate", "trivia", "joke",
])


# ── Booking signals ────────────────────────────────────────────────────────
_STRONG_BOOK_SIGNALS = re.compile(
    r"\b(book\s+a\s+call|schedule\s+a\s+consultation|schedule\s+a\s+meeting|book\s+a\s+discovery\s+call|talk\s+to\s+someone)\b",
    re.IGNORECASE,
)

_BOOK_SIGNALS = re.compile(
    r"\b(book|schedule|set up|arrange|calendar|meeting|call|slot|appointment"
    r"|talk to someone|speak with|connect me|get in touch|reach out)\b",
    re.IGNORECASE,
)

# ── Greeting / ack detector ────────────────────────────────────────────────
_GREETING_RE = re.compile(
    r"^(hi+|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|yo|sup|what'?s\s+up)[!.,?]*$",
    re.IGNORECASE,
)
_ACK_RE = re.compile(
    r"^(thanks?|thank\s+you|ok(?:ay)?|got\s+it|understood|makes?\s+sense"
    r"|sounds?\s+good|cool|great|nice|perfect|alright|sure|yep|yup|nope"
    r"|no\s+thanks?|not\s+now)[!.,?]*$",
    re.IGNORECASE,
)

# ── Agicent knowledge signals (needs retrieval) ────────────────────────────
_KNOWLEDGE_SIGNALS = re.compile(
    r"\b(service|services|case\s+stud|portfolio|pricing|rate|cost|technolog"
    r"|stack|approach|team\s+model|staff\s+augmentation|dedicated\s+team"
    r"|fractional\s+cto|capabilities|offer|expertise|client|industry|deliver"
    r"|agicent|methodology|engagement\s+model|offshore|mvp\s+scope|timeline\b"
    r"|who\s+(?:is|are)|what\s+(?:is|are|does|can))\b",
    re.IGNORECASE,
)

# ── Vague opener that needs discovery ─────────────────────────────────────
_VAGUE_RE = re.compile(
    r"^(i\s+want\s+to|i(?:'m|\s+am)\s+(?:trying|looking|thinking|planning|building|working)"
    r"|we\s+(?:want|need|are\s+building|are\s+planning|have\s+an?\s+idea)"
    r"|can\s+(?:you\s+help|agicent)|help\s+me|need\s+help)[^\?]{0,60}$",
    re.IGNORECASE,
)


def decide(
    query: str,
    state: "ConversationState",
) -> AgentAction:
    """
    Deterministic action selection. Called once per turn before any LLM call.
    """
    q = query.strip()
    q_lower = q.lower()

    # 1. Off-topic guard — fastest exit
    if _is_off_topic(q_lower):
        return AgentAction.REDIRECT_TO_DOMAIN

    # 2. Explicit booking intent
    if _STRONG_BOOK_SIGNALS.search(q_lower):
        return AgentAction.BOOK_CALL

    if _BOOK_SIGNALS.search(q_lower) and state.turn_count >= 2:
        return AgentAction.BOOK_CALL

    # 3. Pure greeting or ack — no retrieval, no discovery
    if _GREETING_RE.match(q) or _ACK_RE.match(q):
        return AgentAction.ASK_DISCOVERY_QUESTION

    # 4. Consultation offer — lead qualified and not yet offered
    if state.should_offer_consultation():
        return AgentAction.OFFER_CONSULTATION

    # 5. Vague opener with no context yet — ask discovery
    if _VAGUE_RE.match(q) and state.lead_score < 20:
        return AgentAction.ASK_DISCOVERY_QUESTION

    # 6. Short question with missing context — keep gathering
    missing = state.next_discovery_field()
    if missing and state.lead_score < 30 and len(q.split()) < 12:
        return AgentAction.ASK_DISCOVERY_QUESTION

    # 7. Question that clearly needs Agicent-specific knowledge
    if _KNOWLEDGE_SIGNALS.search(q_lower):
        return AgentAction.RETRIEVE_AND_ANSWER

    # 8. Enough context available — give recommendation without retrieval
    if state.lead_score >= 30 and state.industry and state.project_type:
        return AgentAction.PROVIDE_RECOMMENDATION

    # Default: retrieve and answer
    return AgentAction.RETRIEVE_AND_ANSWER


def _is_off_topic(q_lower: str) -> bool:
    """True if query is clearly outside Agicent's domain."""
    return any(signal in q_lower for signal in _OFF_TOPIC_SIGNALS)
