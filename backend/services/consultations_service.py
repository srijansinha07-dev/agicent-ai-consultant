from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Iterable

import requests
from filelock import FileLock
from groq import Groq

from config import (
    CONSULTATIONS_FILE,
    CONSULTATION_FORWARD_URL,
    GROQ_API_KEY,
    GROQ_MODEL,
    USE_GROQ,
)
from models import ConsultationConversationItem


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_email(email: str) -> bool:
    e = (email or "").strip()
    return "@" in e and "." in e.split("@")[-1]


def _extract_user_texts(conversation_history: list[ConsultationConversationItem]) -> list[str]:
    user_texts: list[str] = []
    for item in conversation_history or []:
        try:
            if (item.role or "").lower() == "user" and (item.content or "").strip():
                user_texts.append(item.content.strip())
        except Exception:
            continue
    return user_texts


def generate_project_summary(conversation_history: list[ConsultationConversationItem]) -> str:
    """
    Concise staff-friendly summary (bullet tags).
    - Uses Groq when configured
    - Falls back to deterministic keyword extraction otherwise
    """

    # Deterministic fallback is cheap and always available.
    fallback_summary = _heuristic_project_summary(conversation_history)

    if not USE_GROQ or not GROQ_API_KEY:
        return fallback_summary

    try:
        user_texts = _extract_user_texts(conversation_history)
        snippet = "\n".join(user_texts[-6:])[:2500]

        prompt = (
            "You are a strict consulting intake summarizer for Agicent staff.\n\n"
            "TASK: Create a concise project summary for internal review.\n"
            "- Output ONLY bullet tags, one per line.\n"
            "- Prefer short phrases (3-8 words) like 'AI MVP', 'Healthcare startup'.\n"
            "- Cover: project type, domain, requested deliverables, and any budget/timeline intent.\n"
            "- Do not write marketing copy.\n\n"
            f"CONVERSATION (user messages only):\n{snippet}\n\n"
            "OUTPUT:\n"
            "- (one line per bullet tag)\n"
        )

        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=140,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw:
            # Ensure it's bullet-like even if the model deviates slightly.
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if lines and all(lines):
                return "\n".join(
                    [ln if ln.startswith("-") else f"- {ln}" for ln in lines[:6]]
                )
    except Exception:
        # Never block intake on summary generation.
        return fallback_summary

    return fallback_summary


def _heuristic_project_summary(conversation_history: list[ConsultationConversationItem]) -> str:
    user_texts = _extract_user_texts(conversation_history)
    q = " ".join(user_texts).lower()

    def has_any(keywords: Iterable[str]) -> bool:
        return any(k in q for k in keywords)

    items: list[str] = []

    if has_any(["mvp", "minimum viable", "prototype", "poc", "po c"]):
        items.append("AI MVP")

    if has_any(["healthcare", "health", "medic", "hospital", "telemedicine"]):
        items.append("Healthcare startup")

    if has_any(["predict", "predictive", "forecast", "churn", "analytics"]):
        items.append("Predictive analytics")

    if has_any(["budget", "cost", "pricing", "price", "$", "estimate", "range", "rate"]):
        items.append("Budget discussion")

    if has_any(["timeline", "timeframe", "weeks", "months", "how soon", "when", "start", "delivery"]):
        items.append("Timeline requested")

    if has_any(["staff augmentation", "team augmentation", "augmentation", "hire", "hiring", "developers", "fractional"]):
        items.append("Team augmentation")

    if has_any(["rag", "llm", "machine learning", "ml", "nlp", "ai", "agent", "chatbot"]):
        items.append("AI implementation")

    if has_any(["product", "feature", "scope", "roadmap", "requirements", "build", "develop", "launch", "kickoff"]):
        items.append("Product development")

    # Add an intent tail when we have MVP but not explicit planning words.
    if any(i == "AI MVP" for i in items) and not any("planning" in x.lower() for x in items):
        if has_any(["plan", "strategy", "approach", "scope", "roadmap"]):
            items.append("MVP planning requested")

    # Dedupe while preserving order.
    seen = set()
    deduped: list[str] = []
    for i in items:
        if i not in seen:
            deduped.append(i)
            seen.add(i)

    if not deduped:
        deduped = ["Consulting intake"]

    return "\n".join([f"- {i}" for i in deduped[:6]])


def _load_all_requests() -> list[dict]:
    if not CONSULTATIONS_FILE.exists():
        return []
    try:
        return json.loads(CONSULTATIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_all_requests(records: list[dict]) -> None:
    lock_path = str(CONSULTATIONS_FILE) + ".lock"
    file_lock = FileLock(lock_path, timeout=5)

    with file_lock:
        tmp_path = str(CONSULTATIONS_FILE) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(CONSULTATIONS_FILE))


def forward_consultation_if_configured(payload: dict) -> None:
    if not CONSULTATION_FORWARD_URL:
        return
    try:
        requests.post(CONSULTATION_FORWARD_URL, json=payload, timeout=5)
    except Exception:
        # Intakes are still persisted; forwarding is best-effort.
        return


def create_consultation_request(
    *,
    user_id: str | None,
    name: str,
    email: str,
    company: str,
    project_description: str,
    budget: str | None,
    timeline: str | None,
    conversation_history: list[ConsultationConversationItem],
    session_id: str | None,
) -> tuple[str, str]:
    if not (name or "").strip():
        raise ValueError("Name is required.")
    if not _validate_email(email):
        raise ValueError("A valid email is required.")
    if not (company or "").strip():
        raise ValueError("Company is required.")
    if len((project_description or "").strip()) < 10:
        raise ValueError("Project description must be at least 10 characters.")

    consultation_id = "cst_" + uuid.uuid4().hex[:18]
    summary = generate_project_summary(conversation_history)

    record = {
        "consultation_id": consultation_id,
        "created_at": _now_iso(),
        "user_id": user_id,
        "session_id": session_id,
        "name": name.strip(),
        "email": email.strip(),
        "company": company.strip(),
        "project_description": project_description.strip(),
        "budget": budget.strip() if budget else None,
        "timeline": timeline.strip() if timeline else None,
        "project_summary": summary,
        "conversation_history": [item.model_dump() for item in conversation_history or []],
    }

    all_requests = _load_all_requests()
    all_requests.append(record)
    _save_all_requests(all_requests)

    forward_consultation_if_configured(record | {"project_summary": summary})

    return consultation_id, summary


def list_consultations(*, user_id: str | None = None) -> list[dict]:
    records = _load_all_requests()
    if user_id:
        return [r for r in records if r.get("user_id") == user_id]
    return records

