"""
services/decision_engine.py
────────────────────────────
Deterministic routing layer for the Agicent consultant agent.

Given the current user message and ConversationState, returns one of:
  ASK_DISCOVERY_QUESTION   — gather missing project context
  RETRIEVE_AND_ANSWER      — use RAG pipeline to answer
  PROVIDE_RECOMMENDATION   — give Agicent-specific recommendation from state
  OFFER_CONSULTATION       — lead qualified; invite to book
  BOOK_CALL                — user explicitly wants to book a call
  REDIRECT_TO_DOMAIN       — off-topic; politely redirect
  HANDLE_CONFUSION         — user is confused; ask for clarification

CORE RULE: User intent always takes priority over discovery flow.
All routing decisions are derived from intent_classifier.Intent.
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
    STATE_ONLY_ANSWER      = "STATE_ONLY_ANSWER"      # no retrieval, uses state+booking only
    PROVIDE_RECOMMENDATION = "PROVIDE_RECOMMENDATION"
    OFFER_CONSULTATION     = "OFFER_CONSULTATION"
    BOOK_CALL              = "BOOK_CALL"
    REDIRECT_TO_DOMAIN     = "REDIRECT_TO_DOMAIN"
    HANDLE_CONFUSION       = "HANDLE_CONFUSION"


# ── Off-topic guard ────────────────────────────────────────────────────────
_OFF_TOPIC_SIGNALS = frozenset([
    "recipe", "cooking", "weather", "sports", "football", "cricket", "tennis",
    "movie", "music", "song", "celebrity", "politics", "election", "president",
    "stock market", "crypto", "bitcoin", "ethereum", "nft", "meme coin",
    "horoscope", "astrology", "religion", "prayer", "god", "relationship advice",
    "dating", "love poem", "write a poem", "diet", "nutrition", "fitness",
    "homework help", "essay writing", "translate", "trivia", "joke",
])

# ── Exported regex used by consultant_agent for secondary checks ───────────
# Keep this for backward compatibility with any imports.
_KNOWLEDGE_SIGNALS = re.compile(
    r"\b(service|services|case\s+stud|portfolio|pricing|rate|cost|technolog"
    r"|stack|approach|team\s+model|staff\s+augmentation|dedicated\s+team"
    r"|fractional\s+cto|capabilities|offer|expertise|client|industry|deliver"
    r"|agicent|methodology|engagement\s+model|offshore|mvp\s+scope"
    r"|who\s+(?:is|are)|what\s+(?:is|are|does|can))\b",
    re.IGNORECASE,
)


def decide(
    query: str,
    state: "ConversationState",
) -> AgentAction:
    """
    Intent-first routing. Classify intent, then map to action.

    Priority order:
      1. Off-topic → REDIRECT
      2. Booking requests → BOOK_CALL
      3. Booking status/management → RETRIEVE_AND_ANSWER (agent handles context)
      4. Consultation status → RETRIEVE_AND_ANSWER
      5. Knowledge questions → RETRIEVE_AND_ANSWER
      6. Confusion → HANDLE_CONFUSION
      7. Consultation offer threshold → OFFER_CONSULTATION
      8. Project discussion / discovery answers → ASK_DISCOVERY_QUESTION or RECOMMEND
      9. Greeting / Ack → ASK_DISCOVERY_QUESTION (contextual welcome)
      10. Vague → ASK_DISCOVERY_QUESTION
      Default: RETRIEVE_AND_ANSWER
    """
    from services.intent_classifier import Intent, classify, is_knowledge_intent, is_booking_intent

    q_lower = query.strip().lower()

    # 1. Off-topic guard — fastest exit
    if _is_off_topic(q_lower):
        return AgentAction.REDIRECT_TO_DOMAIN

    # 2. Classify intent
    intent = classify(query, state)

    # 3. Booking request — immediate
    if intent == Intent.BOOKING_REQUEST:
        return AgentAction.BOOK_CALL

    # 4. Booking status / management — state only, NO retrieval
    if intent in (Intent.BOOKING_STATUS, Intent.BOOKING_MANAGEMENT):
        return AgentAction.STATE_ONLY_ANSWER

    # 5. Consultation status — state only, NO retrieval
    if intent == Intent.CONSULTATION_STATUS:
        return AgentAction.STATE_ONLY_ANSWER

    # 6. All knowledge intents → retrieval (never blocked by discovery)
    if is_knowledge_intent(intent):
        return AgentAction.RETRIEVE_AND_ANSWER

    # 7. Confusion → dedicated handler
    if intent == Intent.CONFUSION:
        return AgentAction.HANDLE_CONFUSION

    # 8. Consultation offer — lead qualified and not yet offered
    if state.should_offer_consultation():
        return AgentAction.OFFER_CONSULTATION

    # 9. Project discussion → discovery or recommendation
    if intent == Intent.PROJECT_DISCUSSION:
        if state.lead_score >= 30 and state.industry and state.project_type:
            return AgentAction.PROVIDE_RECOMMENDATION
        return AgentAction.ASK_DISCOVERY_QUESTION

    # 10. Discovery answer → continue gathering or recommend
    if intent == Intent.DISCOVERY_ANSWER:
        if state.lead_score >= 30 and state.industry and state.project_type:
            return AgentAction.PROVIDE_RECOMMENDATION
        if state.next_discovery_field():
            return AgentAction.ASK_DISCOVERY_QUESTION
        return AgentAction.RETRIEVE_AND_ANSWER

    # 11. Greeting / Ack → contextual discovery
    if intent in (Intent.GREETING, Intent.ACKNOWLEDGEMENT):
        return AgentAction.ASK_DISCOVERY_QUESTION

    # 12. Vague → discovery
    if intent == Intent.VAGUE:
        return AgentAction.ASK_DISCOVERY_QUESTION

    # Default: retrieve and answer
    return AgentAction.RETRIEVE_AND_ANSWER


def _is_off_topic(q_lower: str) -> bool:
    """True if query is clearly outside Agicent's domain."""
    return any(signal in q_lower for signal in _OFF_TOPIC_SIGNALS)
