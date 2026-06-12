"""
services/conversation_state.py
───────────────────────────────
Per-session conversation state for the Agicent consultant agent.

Stores:
  - Discovered project context (industry, type, users, budget, timeline…)
  - Lead qualification score (0–100)
  - Consultation / booking status
  - Rolling summary for token-efficient history compression
  - Turn counter

Storage: in-memory dict with TTL-based eviction (no Redis dependency).
For multi-worker deployments, plug in a Redis backend by replacing
_load() / _save() with redis.get/set calls.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

from config import CONVERSATION_STATE_TTL_SECONDS


# ── Scoring weights ────────────────────────────────────────────────────────
_SCORE_BUDGET        = 20
_SCORE_TIMELINE      = 20
_SCORE_INDUSTRY      = 15
_SCORE_PROJECT_TYPE  = 15
_SCORE_TARGET_USERS  = 10
_SCORE_COMPANY_STAGE = 10
_SCORE_REQUIREMENTS  = 10   # awarded when len(requirements) >= 3

# Threshold above which we should offer a consultation.
CONSULTATION_OFFER_THRESHOLD = 55


# ── Signal extractors (deterministic, zero LLM) ───────────────────────────

_INDUSTRY_SIGNALS: dict[str, str] = {
    "healthcare":     "healthcare",
    "health":         "healthcare",
    "medic":          "healthcare",
    "hospital":       "healthcare",
    "telemedicine":   "healthcare",
    "fintech":        "fintech",
    "finance":        "fintech",
    "banking":        "fintech",
    "payment":        "fintech",
    "edtech":         "edtech",
    "education":      "edtech",
    "ecommerce":      "ecommerce",
    "retail":         "ecommerce",
    "logistics":      "logistics",
    "supply chain":   "logistics",
    "real estate":    "real_estate",
    "proptech":       "real_estate",
    "hr":             "hr_tech",
    "hrtech":         "hr_tech",
    "saas":           "saas",
    "b2b":            "b2b_saas",
    "enterprise":     "enterprise",
    "startup":        "startup",
    "iot":            "iot",
    "legaltech":      "legaltech",
    "legal":          "legaltech",
    "insurtech":      "insurtech",
    "insurance":      "insurtech",
    "travel":         "travel",
    "hospitality":    "travel",
    "media":          "media",
    "streaming":      "media",
    "gaming":         "gaming",
}

_PROJECT_TYPE_SIGNALS: dict[str, str] = {
    "mvp":              "mvp",
    "minimum viable":   "mvp",
    "prototype":        "prototype",
    "poc":              "poc",
    "proof of concept": "poc",
    "scale":            "scaling",
    "scaling":          "scaling",
    "rewrite":          "rewrite",
    "migration":        "migration",
    "moderniz":         "modernization",
    "redesign":         "redesign",
    "mobile app":       "mobile_app",
    "web app":          "web_app",
    "ai agent":         "ai_agent",
    "chatbot":          "chatbot",
    "recommendation":   "recommendation_system",
    "dashboard":        "dashboard",
    "api":              "api_backend",
    "platform":         "platform",
    "marketplace":      "marketplace",
    "saas product":     "saas_product",
}

_COMPANY_STAGE_SIGNALS: dict[str, str] = {
    "pre-seed":     "pre_seed",
    "preseed":      "pre_seed",
    "seed":         "seed",
    "series a":     "series_a",
    "series b":     "series_b",
    "early stage":  "early_stage",
    "growth stage": "growth_stage",
    "enterprise":   "enterprise",
    "bootstrapped": "bootstrapped",
    "venture":      "venture_backed",
    "vc backed":    "venture_backed",
}

_BUDGET_RE = re.compile(
    r"(\$[\d,.]+[kKmM]?|\d[\d,.]*\s*(?:k|K|m|M|thousand|million|hundred thousand)?"
    r"(?:\s*(?:dollars?|usd|gbp|eur))?|\d[\d,.]*\s*[-–]\s*\d[\d,.]*\s*(?:k|K|m|M)?)",
    re.IGNORECASE,
)

_TIMELINE_RE = re.compile(
    r"\b(\d+[\–-]?\d*\s*(?:week|month|day|sprint|quarter|year)s?"
    r"|q[1-4]\s*\d{4}|[1-4]\s*months?|asap|urgent|immediately)\b",
    re.IGNORECASE,
)

_TARGET_USERS_SIGNALS = (
    "patient", "provider", "doctor", "nurse", "consumer", "business",
    "enterprise", "b2b", "b2c", "end user", "customer", "client",
    "student", "teacher", "driver", "merchant", "investor", "startup",
    "sme", "smb", "admin", "employee", "manager", "hr team",
)


def _extract_signals(text: str) -> dict:
    """Extract project context signals from a user message. Zero LLM tokens."""
    q = text.lower()
    signals: dict = {}

    # Industry
    for keyword, label in _INDUSTRY_SIGNALS.items():
        if keyword in q:
            signals["industry"] = label
            break

    # Project type
    for keyword, label in _PROJECT_TYPE_SIGNALS.items():
        if keyword in q:
            signals["project_type"] = label
            break

    # Company stage
    for keyword, label in _COMPANY_STAGE_SIGNALS.items():
        if keyword in q:
            signals["company_stage"] = label
            break

    # Budget
    m = _BUDGET_RE.search(text)
    if m:
        signals["budget"] = m.group(0).strip()

    # Timeline
    m2 = _TIMELINE_RE.search(text)
    if m2:
        signals["timeline"] = m2.group(0).strip()

    # Target users
    for signal in _TARGET_USERS_SIGNALS:
        if signal in q:
            signals["target_users"] = signal
            break

    return signals


# ── State dataclass ────────────────────────────────────────────────────────

@dataclass
class ConversationState:
    # ── Discovery fields ─────────────────────────────────────────
    industry:          Optional[str]       = None
    project_type:      Optional[str]       = None
    target_users:      Optional[str]       = None
    budget:            Optional[str]       = None
    timeline:          Optional[str]       = None
    company_stage:     Optional[str]       = None
    business_model:    Optional[str]       = None
    requirements:      list[str]           = field(default_factory=list)
    constraints:       list[str]           = field(default_factory=list)
    lead_score:        int                 = 0

    # ── Booking / consultation ────────────────────────────────────
    consultation_offered:   bool           = False
    consultation_requested: bool           = False
    booking_status:         Optional[str]  = None   # None | "offered" | "collecting" | "booked"
    meeting_time:           Optional[str]  = None
    user_email:             Optional[str]  = None
    active_booking:         Optional[dict] = None   # Lightweight injected booking metadata

    # ── Memory ───────────────────────────────────────────────────
    conversation_summary: str              = ""
    turn_count:           int              = 0
    last_active:          float            = field(default_factory=time.time)

    # ── Internal ─────────────────────────────────────────────────
    # Fields already asked so we don't repeat the same discovery question.
    asked_fields: set[str]                 = field(default_factory=set)


    def update_from_message(self, user_text: str) -> None:
        """Extract signals from user message and merge into state."""
        signals = _extract_signals(user_text)
        if signals.get("industry") and not self.industry:
            self.industry = signals["industry"]
        if signals.get("project_type") and not self.project_type:
            self.project_type = signals["project_type"]
        if signals.get("company_stage") and not self.company_stage:
            self.company_stage = signals["company_stage"]
        if signals.get("budget") and not self.budget:
            self.budget = signals["budget"]
        if signals.get("timeline") and not self.timeline:
            self.timeline = signals["timeline"]
        if signals.get("target_users") and not self.target_users:
            self.target_users = signals["target_users"]

        self.turn_count += 1
        self.last_active = time.time()
        self._recalculate_score()

    def _recalculate_score(self) -> None:
        score = 0
        if self.budget:             score += _SCORE_BUDGET
        if self.timeline:           score += _SCORE_TIMELINE
        if self.industry:           score += _SCORE_INDUSTRY
        if self.project_type:       score += _SCORE_PROJECT_TYPE
        if self.target_users:       score += _SCORE_TARGET_USERS
        if self.company_stage:      score += _SCORE_COMPANY_STAGE
        if len(self.requirements) >= 3:
                                    score += _SCORE_REQUIREMENTS
        self.lead_score = min(score, 100)

    def should_offer_consultation(self) -> bool:
        return (
            self.lead_score >= CONSULTATION_OFFER_THRESHOLD
            and not self.consultation_offered
            and not self.consultation_requested
        )

    def next_discovery_field(self) -> Optional[str]:
        """Return the next most important field to ask about."""
        priority = [
            "industry",
            "project_type",
            "target_users",
            "timeline",
            "budget",
            "company_stage",
        ]
        for f in priority:
            if getattr(self, f) is None and f not in self.asked_fields:
                return f
        return None

    def mark_asked(self, field_name: str) -> None:
        self.asked_fields.add(field_name)

    def to_context_snippet(self) -> str:
        """Build a compact context string for LLM prompts (~80 tokens max)."""
        project_parts = []
        if self.industry:       project_parts.append(f"Industry: {self.industry}")
        if self.project_type:   project_parts.append(f"Project: {self.project_type}")
        if self.target_users:   project_parts.append(f"Users: {self.target_users}")
        if self.budget:         project_parts.append(f"Budget: {self.budget}")
        if self.timeline:       project_parts.append(f"Timeline: {self.timeline}")
        if self.company_stage:  project_parts.append(f"Stage: {self.company_stage}")
        if self.requirements:   project_parts.append(f"Needs: {'; '.join(self.requirements[:3])}")
        if self.conversation_summary:
            project_parts.append(f"Summary: {self.conversation_summary}")

        sections = []
        if project_parts:
            sections.append("[PROJECT] " + " | ".join(project_parts))

        if self.active_booking:
            b = self.active_booking
            booking_lines = []
            if b.get("date"):       booking_lines.append(f"Date: {b['date']}")
            if b.get("time"):       booking_lines.append(f"Time: {b['time']}")
            if b.get("consultant"): booking_lines.append(f"Consultant: {b['consultant']}")
            if b.get("meet_link"):  booking_lines.append(f"Google Meet: {b['meet_link']}")
            if b.get("status"):     booking_lines.append(f"Status: {b['status']}")
            if booking_lines:
                sections.append("[ACTIVE BOOKING] " + " | ".join(booking_lines))

        return "\n".join(sections) if sections else ""


# ── In-memory store with TTL ───────────────────────────────────────────────

_store: dict[str, ConversationState] = {}


def get_or_create(session_id: str) -> ConversationState:
    """Return existing state or create a fresh one for this session."""
    _evict_expired()
    if session_id not in _store:
        _store[session_id] = ConversationState()
    return _store[session_id]


def update(session_id: str, state: ConversationState) -> None:
    """Persist updated state back (no-op for in-memory, but explicit for readability)."""
    state.last_active = time.time()
    _store[session_id] = state


def _evict_expired() -> None:
    """Remove sessions that have been idle longer than TTL."""
    now = time.time()
    ttl = CONVERSATION_STATE_TTL_SECONDS
    expired = [sid for sid, s in _store.items() if now - s.last_active > ttl]
    for sid in expired:
        del _store[sid]
