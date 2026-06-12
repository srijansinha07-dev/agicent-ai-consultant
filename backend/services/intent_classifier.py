"""
services/intent_classifier.py
──────────────────────────────
Fine-grained intent classification for every incoming user message.

Intent is evaluated BEFORE any discovery, routing, or retrieval decision.
User intent always takes priority over discovery flow.

Intent taxonomy (ordered by priority at decision time):
  BOOKING_REQUEST      — user explicitly wants to book a discovery call
  BOOKING_STATUS       — user asking about their booking confirmation/details
  BOOKING_MANAGEMENT   — user wants to cancel/reschedule a booking
  CONSULTATION_STATUS  — user asking whether their consultation form was received
  KNOWLEDGE_COMPANY    — what does Agicent do / who are you
  KNOWLEDGE_SERVICES   — what services do you offer
  KNOWLEDGE_TECHNOLOGY — what tech stack / technologies do you use
  KNOWLEDGE_PRICING    — pricing / cost / rates
  KNOWLEDGE_CASE_STUDY — show me case studies / portfolio / examples
  KNOWLEDGE_PROCESS    — what is your development process / methodology
  PROJECT_DISCUSSION   — user describing their project or need (contextual)
  DISCOVERY_ANSWER     — user directly answering a discovery question
  CONFUSION            — user is confused, asked to clarify, or replied with noise
  GREETING             — hello / hi / hey
  ACKNOWLEDGEMENT      — ok / thanks / sounds good / got it
  GENERAL_QUESTION     — anything else that's a real question
  VAGUE                — too vague to classify (needs discovery)
"""
from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.conversation_state import ConversationState


class Intent(str, Enum):
    BOOKING_REQUEST      = "BOOKING_REQUEST"
    BOOKING_STATUS       = "BOOKING_STATUS"
    BOOKING_MANAGEMENT   = "BOOKING_MANAGEMENT"
    CONSULTATION_STATUS  = "CONSULTATION_STATUS"
    KNOWLEDGE_COMPANY    = "KNOWLEDGE_COMPANY"
    KNOWLEDGE_SERVICES   = "KNOWLEDGE_SERVICES"
    KNOWLEDGE_TECHNOLOGY = "KNOWLEDGE_TECHNOLOGY"
    KNOWLEDGE_PRICING    = "KNOWLEDGE_PRICING"
    KNOWLEDGE_CASE_STUDY = "KNOWLEDGE_CASE_STUDY"
    KNOWLEDGE_PROCESS    = "KNOWLEDGE_PROCESS"
    PROJECT_DISCUSSION   = "PROJECT_DISCUSSION"
    DISCOVERY_ANSWER     = "DISCOVERY_ANSWER"
    CONFUSION            = "CONFUSION"
    GREETING             = "GREETING"
    ACKNOWLEDGEMENT      = "ACKNOWLEDGEMENT"
    GENERAL_QUESTION     = "GENERAL_QUESTION"
    VAGUE                = "VAGUE"


# ── Compiled patterns ──────────────────────────────────────────────────────

_BOOKING_REQUEST_RE = re.compile(
    r"\b(book\s+a?\s+call|book\s+a?\s+meeting|schedule\s+a?\s+(?:call|meeting|consultation|session|discovery)"
    r"|set\s+up\s+a?\s+call|arrange\s+a?\s+call|get\s+a?\s+(?:call|slot|appointment)"
    r"|talk\s+to\s+(?:someone|a\s+consultant|the\s+team)|speak\s+with|connect\s+me"
    r"|reach\s+out|get\s+in\s+touch|book\s+a?\s+discovery|i\s+want\s+to\s+book)\b",
    re.IGNORECASE,
)

_BOOKING_STATUS_RE = re.compile(
    r"\b(is\s+my\s+booking|booking\s+confirm|call\s+confirm"
    r"|when\s+is\s+my\s+(?:call|meeting|discovery|appointment|booking)"
    r"|what\s+time\s+is\s+my\s+(?:call|meeting|discovery|appointment)"
    r"|who\s+am\s+i\s+(?:meeting|talking\s+to)|did\s+my\s+booking"
    r"|my\s+appointment|booking\s+go\s+through|booking\s+scheduled"
    r"|see\s+my\s+booking|details\s+of\s+my\s+(?:booking|call|meeting))\b",
    re.IGNORECASE,
)

_BOOKING_MANAGEMENT_RE = re.compile(
    r"\b(cancel\s+(?:my\s+)?(?:booking|call|meeting|appointment)"
    r"|reschedule\s+(?:my\s+)?(?:booking|call|meeting|appointment)"
    r"|change\s+(?:my\s+)?(?:booking|call|meeting|appointment|time|slot)"
    r"|move\s+(?:my\s+)?(?:call|meeting|appointment))\b",
    re.IGNORECASE,
)

_CONSULTATION_STATUS_RE = re.compile(
    r"\b(did\s+(?:you|my)\s+(?:receive|get|send)\s+(?:my\s+)?(?:consultation|request|form)"
    r"|consultation\s+(?:submitted|received|sent|pending|status)"
    r"|did\s+my\s+(?:consultation|request)\s+go\s+through"
    r"|has\s+(?:the|my)\s+(?:request|consultation)\s+been\s+received"
    r"|(?:status|update)\s+(?:of|on)\s+my\s+(?:consultation|request)"
    r"|what\s+(?:happened|is\s+happening)\s+(?:to|with)\s+my\s+(?:consultation|request)"
    r"|form\s+(?:submitted|received|sent))\b",
    re.IGNORECASE,
)

_KNOWLEDGE_COMPANY_RE = re.compile(
    r"\b(what\s+(?:is|does)\s+agicent|who\s+(?:is|are)\s+agicent|about\s+agicent"
    r"|agicent\s+(?:company|overview|intro|background|founded|mission)"
    r"|tell\s+me\s+about\s+(?:agicent|you|your\s+company)"
    r"|what\s+do\s+you\s+do|who\s+are\s+you)\b",
    re.IGNORECASE,
)

_KNOWLEDGE_SERVICES_RE = re.compile(
    r"\b(what\s+(?:services|offerings)\s+(?:do\s+you|does\s+agicent)|your\s+services"
    r"|what\s+(?:can\s+you|do\s+you)\s+(?:build|develop|offer|provide|deliver)"
    r"|service\s+offerings?|what\s+do\s+you\s+(?:offer|provide|specialize)"
    r"|capabilities|what\s+are\s+your\s+(?:capabilities|offerings)"
    r"|staff\s+augmentation|dedicated\s+team|fractional\s+cto|team\s+model"
    r"|offshore|engagement\s+model)\b",
    re.IGNORECASE,
)

_KNOWLEDGE_TECHNOLOGY_RE = re.compile(
    r"\b(what\s+(?:tech|technologies?|stack|frameworks?|languages?|tools?)"
    r"|tech(?:nology)?\s+stack|which\s+(?:technologies?|frameworks?|languages?)"
    r"|do\s+you\s+(?:use|work\s+with|support)\s+(?:react|flutter|python|node|swift|kotlin|aws|gcp|azure)"
    r"|react\s+native|flutter|swift|kotlin|typescript|python|django|fastapi|golang"
    r"|machine\s+learning|llm|rag|generative\s+ai|ai\s+(?:tools?|stack|framework))\b",
    re.IGNORECASE,
)

_KNOWLEDGE_PRICING_RE = re.compile(
    r"\b((?:what\s+(?:is|are)|how\s+much|tell\s+me\s+about)\s+(?:your\s+)?(?:pricing|rates?|costs?|fees?|price))"
    r"|(pricing|rates?|cost\s+to\s+(?:build|hire|develop)|how\s+much\s+(?:does|would|will)\s+it\s+cost"
    r"|budget\s+(?:estimate|range|ballpark)|hourly\s+rate|monthly\s+rate"
    r"|engagement\s+(?:pricing|cost)|what\s+do\s+you\s+charge)\b",
    re.IGNORECASE,
)

_KNOWLEDGE_CASE_STUDY_RE = re.compile(
    r"\b(case\s+stud(?:y|ies)|portfolio|previous\s+(?:work|projects?|clients?)"
    r"|(?:show|share)\s+(?:me\s+)?(?:some\s+)?(?:examples?|projects?|work|case\s+studies?)"
    r"|examples?\s+(?:of|from)|similar\s+(?:projects?|work|clients?)"
    r"|who\s+(?:have\s+you|has\s+agicent)\s+(?:worked\s+with|built\s+for|delivered\s+for)"
    r"|past\s+(?:projects?|clients?|work)|client\s+(?:success|stories?|examples?))\b",
    re.IGNORECASE,
)

_KNOWLEDGE_PROCESS_RE = re.compile(
    r"\b((?:your|agicent(?:'s)?)\s+(?:process|methodology|approach|workflow|framework)"
    r"|how\s+(?:do\s+you|does\s+agicent)\s+(?:work|deliver|build|develop|approach)"
    r"|development\s+process|delivery\s+(?:process|model|approach)"
    r"|how\s+(?:does|would)\s+(?:a\s+)?(?:project|engagement)\s+(?:work|run|start|begin))\b",
    re.IGNORECASE,
)

_CONFUSION_RE = re.compile(
    r"^(\?+|what\??|huh\??|what\s+do\s+you\s+mean\??|can\s+you\s+explain\??|not\s+sure\??|don'?t\s+understand\??|idk\??|i\s+don'?t\s+know\??|unclear\??|confused\??|sorry\s+what\??|pardon\??|repeat\s+that\??)\??[!.]*$",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^(hi+|hello+|hey+|good\s+(?:morning|afternoon|evening)|howdy|yo+|sup|what'?s\s+up|greetings|hiya)[!.,?]*$",
    re.IGNORECASE,
)

_ACK_RE = re.compile(
    r"^(thanks?(?:\s+(?:a\s+lot|so\s+much|very\s+much))?|thank\s+you(?:\s+so\s+much)?"
    r"|ok(?:ay)?(?:\s+got\s+it)?|got\s+it|understood|makes?\s+sense"
    r"|sounds?\s+(?:good|great|perfect|right)|cool(?:\s+got\s+it)?"
    r"|great(?:\s+thanks?)?|nice(?:\s+one)?|perfect|alright(?:\s+got\s+it)?"
    r"|sure(?:\s+thing)?|yep|yup|nope|no\s+thanks?|not\s+now"
    r"|noted|k\b|kk|all\s+good|that(?:'s|\s+is)\s+(?:good|great|clear|helpful|fine))[!.,?]*$",
    re.IGNORECASE,
)

_PROJECT_SIGNALS_RE = re.compile(
    r"\b(i(?:'m|\s+am)\s+(?:building|working\s+on|developing|creating|launching|starting)"
    r"|we\s+(?:are|have)\s+(?:building|working\s+on|developing|creating)"
    r"|(?:building|developing|creating|launching)\s+a(?:n)?\s+"
    r"|our\s+(?:product|app|platform|startup|company)\s+(?:is|does|needs)"
    r"|i\s+have\s+(?:a|an)\s+(?:project|product|app|idea|startup|platform)"
    r"|we\s+(?:want|need)\s+to\s+(?:build|develop|create|launch))\b",
    re.IGNORECASE,
)

_VAGUE_RE = re.compile(
    r"^(i\s+want\s+(?:to\s+)?(?:build|start|create|launch|develop)?$"
    r"|need\s+help$|help\s+me$|looking\s+for\s+help$"
    r"|i\s+need\s+(?:a\s+)?(?:developer|team|help)$"
    r"|(?:can|could)\s+you\s+help(?:\s+me)?$"
    r"|we\s+(?:need|want)\s+(?:help|assistance)$)[.!?]*$",
    re.IGNORECASE,
)


def classify(query: str, state: "ConversationState") -> Intent:
    """
    Classify the intent of a user message.
    Priority order enforces: booking > knowledge > project context > confusion > vague.
    """
    q = query.strip()
    ql = q.lower()

    # 1. Greeting — pure greeting only
    if _GREETING_RE.match(q):
        return Intent.GREETING

    # 2. Acknowledgement — pure ack only
    if _ACK_RE.match(q):
        return Intent.ACKNOWLEDGEMENT

    # 3. Confusion — user clearly confused or asking for clarification
    if _CONFUSION_RE.match(q):
        return Intent.CONFUSION

    # 4. Booking intents (highest priority after social signals)
    if _BOOKING_MANAGEMENT_RE.search(ql):
        return Intent.BOOKING_MANAGEMENT
    if _BOOKING_STATUS_RE.search(ql):
        return Intent.BOOKING_STATUS
    if _BOOKING_REQUEST_RE.search(ql):
        return Intent.BOOKING_REQUEST

    # 5. Consultation status
    if _CONSULTATION_STATUS_RE.search(ql):
        return Intent.CONSULTATION_STATUS

    # 6. Knowledge intents — always answered before discovery
    if _KNOWLEDGE_CASE_STUDY_RE.search(ql):
        return Intent.KNOWLEDGE_CASE_STUDY
    if _KNOWLEDGE_COMPANY_RE.search(ql):
        return Intent.KNOWLEDGE_COMPANY
    if _KNOWLEDGE_PRICING_RE.search(ql):
        return Intent.KNOWLEDGE_PRICING
    if _KNOWLEDGE_TECHNOLOGY_RE.search(ql):
        return Intent.KNOWLEDGE_TECHNOLOGY
    if _KNOWLEDGE_PROCESS_RE.search(ql):
        return Intent.KNOWLEDGE_PROCESS
    if _KNOWLEDGE_SERVICES_RE.search(ql):
        return Intent.KNOWLEDGE_SERVICES

    # 7. Project discussion — user describing their own project/needs
    if _PROJECT_SIGNALS_RE.search(ql):
        return Intent.PROJECT_DISCUSSION

    # 8. Discovery answer — short reply that could be answering a prior discovery question
    #    Only fires if a discovery question was recently asked (from state)
    if state.asked_fields and _is_discovery_answer(q, state):
        return Intent.DISCOVERY_ANSWER

    # 9. Vague opener
    if _VAGUE_RE.match(q) or (len(q.split()) <= 4 and '?' not in q and not _PROJECT_SIGNALS_RE.search(ql)):
        return Intent.VAGUE

    # 10. Generic question — has '?' or is a substantive query
    if '?' in q or len(q.split()) >= 5:
        return Intent.GENERAL_QUESTION

    return Intent.VAGUE


def _is_discovery_answer(query: str, state: "ConversationState") -> bool:
    """
    Heuristic: is this short reply likely answering the last discovery question?
    Avoid advancing discovery on confusion/noise signals.
    """
    ql = query.strip().lower()

    # Explicit confusion signals should not count as answers
    confusion_signals = (
        "?", "what", "huh", "idk", "not sure", "don't know",
        "unclear", "explain", "what do you mean", "what does that mean",
        "sorry", "pardon", "repeat",
    )
    if any(sig in ql for sig in confusion_signals):
        return False

    # Short substantive reply is likely an answer if we recently asked something
    word_count = len(query.split())
    return word_count >= 1 and word_count <= 20 and bool(state.asked_fields)


def is_knowledge_intent(intent: Intent) -> bool:
    """True if the intent requires RAG retrieval to answer."""
    return intent in {
        Intent.KNOWLEDGE_COMPANY,
        Intent.KNOWLEDGE_SERVICES,
        Intent.KNOWLEDGE_TECHNOLOGY,
        Intent.KNOWLEDGE_PRICING,
        Intent.KNOWLEDGE_CASE_STUDY,
        Intent.KNOWLEDGE_PROCESS,
        Intent.GENERAL_QUESTION,
    }


def is_booking_intent(intent: Intent) -> bool:
    """True if the intent is booking-related."""
    return intent in {
        Intent.BOOKING_REQUEST,
        Intent.BOOKING_STATUS,
        Intent.BOOKING_MANAGEMENT,
    }


def needs_discovery(intent: Intent) -> bool:
    """True if discovery questioning is appropriate for this intent."""
    return intent in {
        Intent.GREETING,
        Intent.VAGUE,
        Intent.PROJECT_DISCUSSION,
        Intent.DISCOVERY_ANSWER,
    }
