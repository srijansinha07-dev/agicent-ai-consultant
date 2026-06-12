"""
services/website_support.py
───────────────────────────
Deterministic helpers for website:// document retrieval and prompting.
Additive only — PDF behavior is unchanged when pdf_path does not start with website://
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import Chunk

# ── Retrieval breadth (website only) ─────────────────────────────────────
WEBSITE_TOP_K_SEMANTIC = 12
WEBSITE_TOP_K_BM25 = 12
WEBSITE_CANDIDATE_CAP = 12
WEBSITE_TOP_K_FINAL = 5
WEBSITE_CONTEXT_CHAR_LIMIT = 2500

# ── Metadata score adjustments (additive, bounded) ─────────────────────────
_URL_BOOSTS: tuple[tuple[str, float], ...] = (
    ("artificial-intelligence", 0.25),
    ("hire-ai", 0.20),
    ("case-study", 0.20),
    ("mobile-app", 0.18),
    ("staff-augmentation", 0.18),
    ("cost-of-app-maintenance", -0.40),
    ("blog/tag", -0.40),
    ("archives", -0.35),
    ("wordpress", -0.30),
    ("maintenance", -0.25),
    ("category", -0.20),
    ("services", 0.15),
    ("development", 0.12),
    ("startup", 0.12),
    ("ai", 0.25),
)

_TITLE_BOOSTS: tuple[tuple[str, float], ...] = (
    ("artificial intelligence", 0.25),
    ("case study", 0.20),
    ("mobile app", 0.18),
    ("staff augmentation", 0.18),
    ("services", 0.15),
    ("development", 0.12),
    ("startup", 0.12),
    ("ai", 0.20),
)

_PENALIZE_ANYWHERE: tuple[tuple[str, float], ...] = (
    ("blog/tag", -0.40),
    ("archives", -0.35),
    ("category", -0.20),
    ("wordpress", -0.30),
    ("maintenance", -0.25),
    ("cost-of-app-maintenance", -0.40),
)

_MAX_METADATA_ADJUSTMENT = 0.55
_MIN_METADATA_ADJUSTMENT = -0.55

_COMPANY_QUERY_SIGNALS = (
    "service",
    "services",
    "pricing",
    "price",
    "capabilit",
    "technolog",
    "hiring",
    "hire",
    "case stud",
    "case-study",
    "offering",
    "offerings",
    "artificial intelligence",
    " ai ",
    "ai ",
    "develop",
    "industr",
    "company",
    "provide",
    "expertise",
    "consult",
    "startup",
    "mobile app",
    "staff augmentation",
    "compare",
    "versus",
    " vs ",
    "model",
    "agicent",
)

_URL_LINE_RE = re.compile(r"^URL:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


def is_website_doc(doc_id: str) -> bool:
    try:
        from services import docstore

        path = docstore.get_pdf_path(doc_id) or ""
        return path.startswith("website://")
    except Exception:
        return False


def is_website_company_query(query: str) -> bool:
    q = f" {query.lower()} "
    return any(sig in q for sig in _COMPANY_QUERY_SIGNALS)


def expand_website_retrieval_query(query: str) -> str:
    """Deterministic retrieval query expansion for company/support intents."""
    q = query.lower()
    extras: list[str] = []

    if "agicent" in q or "company" in q or "provide" in q or "offer" in q:
        extras.append("Agicent")

    if any(t in q for t in ("service", "services", "offering", "capabilit", "provide")):
        extras.extend([
            "AI services",
            "app development",
            "web development",
            "digital transformation",
            "staff augmentation",
        ])

    if any(t in q for t in ("ai", "artificial intelligence", "machine learning", "generative")):
        extras.extend([
            "generative AI",
            "predictive analytics",
            "AI consulting",
            "AI development",
            "machine learning",
        ])

    if any(t in q for t in ("pricing", "price", "cost", "rate")):
        extras.extend(["pricing", "rates", "engagement models"])

    if any(t in q for t in ("technolog", "stack", "framework")):
        extras.extend([
            "React Native",
            "Flutter",
            "Python",
            "cloud",
            "technologies",
        ])

    if any(t in q for t in ("hiring", "hire", "staff", "augmentation", "team", "model")):
        extras.extend([
            "hiring models",
            "dedicated developers",
            "offshore team",
            "staff augmentation",
            "fractional CTO",
        ])

    if any(t in q for t in ("case stud", "case-study", "portfolio", "client")):
        extras.extend(["case studies", "client success", "portfolio"])

    if any(t in q for t in ("industr", "vertical", "domain", "sector")):
        extras.extend([
            "industries",
            "healthcare",
            "fintech",
            "IoT",
            "telemedicine",
            "startups",
        ])

    if any(t in q for t in ("compare", " vs ", "versus", "difference")):
        extras.extend([
            "app development",
            "AI development",
            "comparison",
            "capabilities",
        ])

    if any(t in q for t in ("mobile", "app dev", "application")):
        extras.extend(["mobile app development", "iOS", "Android", "MVP"])

    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in extras:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if not unique:
        return query
    return f"{query} {' '.join(unique)}"


def extract_website_metadata(chunk: "Chunk") -> tuple[str, str, str]:
    """
    Parse URL, title, and heading hints from website chunk text.
    Website ingest format: title, blank, URL: ..., headings line, content.
    """
    text = chunk.text or ""
    url = ""
    m = _URL_LINE_RE.search(text)
    if m:
        url = m.group(1).strip().lower()

    title = ""
    if m:
        prefix = text[: m.start()].strip()
        lines = [ln.strip() for ln in prefix.splitlines() if ln.strip()]
        if lines:
            title = lines[0]
    elif text:
        first = text.splitlines()[0].strip()
        if first and not first.lower().startswith("url:"):
            title = first

    heading = (chunk.section_heading or "").lower()
    if not heading and m:
        after = text[m.end() :].strip().splitlines()
        if after:
            candidate = after[0].strip()
            if candidate and "|" in candidate and len(candidate) < 400:
                heading = candidate.lower()

    return url, title, heading


def apply_website_metadata_boosts(chunk: "Chunk") -> None:
    """Additive score adjustments from URL/title/heading (website docs only)."""
    url, title, heading = extract_website_metadata(chunk)
    meta = f"{url} {title.lower()} {heading}".strip()
    if not meta:
        return

    adjustment = 0.0

    for term, delta in _URL_BOOSTS:
        if term in url:
            adjustment += delta

    for term, delta in _TITLE_BOOSTS:
        if term in title.lower():
            adjustment += delta

    for term, delta in _PENALIZE_ANYWHERE:
        if term in meta:
            adjustment += delta

    adjustment = max(_MIN_METADATA_ADJUSTMENT, min(_MAX_METADATA_ADJUSTMENT, adjustment))
    chunk.score += adjustment


# URL slug → human-readable source label (longest / most specific matches first)
_SLUG_LABEL_MAP: tuple[tuple[str, str], ...] = (
    ("artificial-intelligence", "Artificial Intelligence"),
    ("hire-ai-developers", "Hire AI Developers"),
    ("hire-ai", "Hire AI Developers"),
    ("generative-ai", "Generative AI"),
    ("machine-learning", "Machine Learning"),
    ("predictive-analytics", "Predictive Analytics"),
    ("case-studies", "Case Studies"),
    ("case-study", "Case Studies"),
    ("mobile-app-development", "Mobile App Development"),
    ("mobile-app", "Mobile App Development"),
    ("staff-augmentation", "Staff Augmentation"),
    ("dedicated-teams", "Dedicated Teams"),
    ("dedicated-team", "Dedicated Teams"),
    ("digital-transformation", "Digital Transformation"),
    ("web-development", "Web Development"),
    ("app-development", "App Development"),
    ("software-development", "Software Development"),
    ("fractional-cto", "Fractional CTO"),
    ("offshore-development", "Offshore Development"),
    ("mvp-development", "MVP Development"),
    ("startup", "Startup Solutions"),
    ("healthcare", "Healthcare"),
    ("fintech", "Fintech"),
    ("iot", "IoT Solutions"),
    ("telemedicine", "Telemedicine"),
    ("pricing", "Pricing & Engagement"),
    ("engagement-model", "Engagement Models"),
    ("about-us", "About Agicent"),
    ("about", "About Agicent"),
    ("contact", "Contact"),
    ("services", "Services"),
)


_LOW_QUALITY_LABELS = frozenset({
    "agicent", "home", "website", "services", "contact", "blog", "category",
    "archives", "wordpress", "tag",
})


def _is_quality_resource_label(label: str) -> bool:
    if not label or len(label) < 12:
        return False
    lower = label.lower().strip()
    if lower in _LOW_QUALITY_LABELS:
        return False
    # Reject raw URL slugs (hyphenated, no spaces)
    if "-" in lower and " " not in lower and not lower.startswith("http"):
        return False
    if re.match(r"^[a-z0-9_/-]+$", lower):
        return False
    return True


def derive_website_source_label(url: str, title: str, heading: str) -> str:
    """Human-readable page title for Related Agicent Resources (empty if low quality)."""
    if title:
        cleaned = _normalize_title(title)
        if _is_quality_resource_label(cleaned):
            return cleaned

    if heading:
        parts = [p.strip() for p in heading.split("|") if p.strip()]
        for part in parts[:2]:
            candidate = _normalize_title(part)
            if _is_quality_resource_label(candidate):
                return candidate

    url_l = (url or "").lower()
    for slug, label in _SLUG_LABEL_MAP:
        if slug in url_l and _is_quality_resource_label(label):
            return label

    return ""


def _normalize_title(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw.strip())
    if not text or len(text) > 100:
        return ""
    if text == text.lower():
        return text.title()
    return text


WEBSITE_SUPPORT_RULES = (
    "You are Agicent's AI Consultant — a knowledgeable AI representative of Agicent (agicent.com).\n"
    "You are NOT a human consultant. Do not claim personal experience, personal opinions, or human identity.\n\n"
    "IDENTITY:\n"
    "- You represent Agicent as an AI system.\n"
    "- Use: 'Based on Agicent\'s experience...', 'Agicent typically approaches...', 'According to Agicent\'s process...'\n"
    "- Never say: 'I personally recommend', 'I have worked on', 'As a senior consultant', 'I can confirm from experience'\n\n"
    "PERSPECTIVE:\n"
    "- Answer from Agicent's viewpoint. Vary sentence openings naturally.\n"
    "- Do not mechanically start replies with 'At Agicent...'.\n"
    "- Prioritize Agicent methodology, services, case studies, and delivery models from CONTEXT.\n"
    "- Generic industry advice is only a brief fallback when context lacks detail.\n\n"
    "TRUTH:\n"
    "- Use ONLY retrieved CONTEXT as primary truth. Do not invent pricing, timelines, or capabilities.\n"
    "- If context is insufficient, say what Agicent can confirm and suggest speaking with the team.\n\n"
    "RESPONSE DISCIPLINE:\n"
    "- Answer the user's actual question directly. Do not pad with sales copy.\n"
    "- Aim for 120-220 words. Shorter is better when the answer is clear.\n"
    "- Avoid: cutting-edge, innovative solutions, bespoke development, end-to-end services, industry-leading.\n"
    "- Use headings or bullets only when they genuinely improve readability.\n\n"
    "TONE:\n"
    "- Professional, direct, and helpful. Think through the problem before answering.\n"
    "- Emphasise practical approach and next steps over generic benefits."
)


# ── Compressed consultant prompt (~80 tokens) ──────────────────────────────
# Used by the new consultant_agent.py to save tokens on every request.
# Behaviorally equivalent to WEBSITE_SUPPORT_RULES but dramatically shorter.
CONSULTANT_PROMPT_COMPRESSED = (
    "You are Agicent's AI Consultant (agicent.com). NOT a human.\n"
    "VOICE: Use 'we'/'our' for Agicent. Use 'I' for yourself. Never say 'Agicent typically', 'According to Agicent', 'They'.\n"
    "LANGUAGE: Never expose: 'context', 'retrieval', 'knowledge-base', 'prompt', 'model'. Speak naturally.\n"
    "RULES:\n"
    "- Answer the user's question first. No preamble. No company background unless asked.\n"
    "- Use known project context to personalise answers. Do not repeat facts already established.\n"
    "- When user describes a project: acknowledge, identify the key unknown, ask ONE focused question.\n"
    "- Only suggest a consultation when discussing implementation, budget, timelines, or project feasibility.\n"
    "- Be concise (100-150 words). Use bullet points for lists."
)


# ── Discovery question templates (zero LLM, deterministic) ────────────────
# One question per missing discovery field. Keep them conversational.
# ── Discovery question banks (contextual, not rigid templates) ────────────
# Each field has multiple variants so the question can be chosen based on
# what the user has already said. consultant_agent picks the most relevant.
DISCOVERY_QUESTIONS: dict[str, str] = {
    # Default (fallback) questions per field — used when no context available
    "industry": "What industry or vertical is this project for?",
    "project_type": "Are you starting fresh, scaling an existing product, or modernising something already in production?",
    "target_users": "Who are the primary users of this product?",
    "timeline": "What timeline are you working with? Is there a specific launch target?",
    "budget": "Do you have a rough budget in mind? Even a ballpark helps narrow down the right team model.",
    "company_stage": "What stage is your company at — early-stage, growth, or enterprise?",
}

# Per-field contextual question variants keyed by known context.
# Format: { field: { context_key: question_text } }
DISCOVERY_QUESTION_VARIANTS: dict[str, dict[str, str]] = {
    "project_type": {
        "healthcare": "Is this a new platform, an upgrade to an existing system, or integration with existing clinical tools?",
        "fintech": "Are you building a new product, adding features to an existing one, or doing a compliance/modernisation project?",
        "edtech": "Are you starting with an MVP, or do you have an existing platform you're looking to scale?",
        "ecommerce": "Are you building a new storefront, scaling your current platform, or adding capabilities like AI recommendations?",
        "saas": "Are you launching a new SaaS, scaling the current product, or modernising the architecture?",
        "startup": "Are you at the idea/MVP stage, or do you have an early product looking to scale?",
    },
    "target_users": {
        "healthcare": "Who will use the platform — patients, clinicians, hospital admins, or all three?",
        "fintech": "Is this aimed at retail consumers, business clients, or financial institutions?",
        "edtech": "Is this for students, educators, institutions, or a mix?",
        "ecommerce": "Is this B2C, B2B, or a marketplace model?",
        "saas": "Who's the primary buyer — individual users, teams, or enterprise?",
    },
    "timeline": {
        "mvp": "What's the target launch for the MVP — are we talking weeks or months?",
        "scaling": "What's driving the timeline? Is there a specific growth milestone or product deadline?",
        "mobile_app": "Do you have a hard launch date in mind, or is the timeline flexible?",
    },
    "budget": {
        "startup": "Do you have a budget range for the initial build? It helps us suggest the right scope.",
        "enterprise": "What's the approximate project budget or engagement budget you're working with?",
        "mvp": "For the MVP phase, what budget range are you working with? Even a rough estimate is helpful.",
    },
}


# ── Domain guardrail response ──────────────────────────────────────────────
DOMAIN_REDIRECT_MESSAGE = (
    "That's outside what I can help with — my focus is software development, "
    "AI products, product strategy, and digital transformation. "
    "If you have a project or technology question, I'm happy to dig into it."
)


# ── Consultation offer templates ────────────────────────────────────────────
CONSULTATION_OFFER_MESSAGES = {
    "default": (
        "Based on what you've shared, this looks like a good fit for a focused discovery session. "
        "Agicent typically uses a 45-minute call to align on scope, team model, and delivery approach "
        "before moving forward.\n\n"
        "Would you like to schedule one?"
    ),
    "high_budget": (
        "With the budget and timeline you've described, Agicent can move quickly. "
        "A discovery call would help nail down the right scope and team structure for your situation.\n\n"
        "Want to set up a 45-minute session?"
    ),
    "mvp": (
        "There's enough context here to start planning. "
        "Agicent's typical next step would be a discovery session to define the MVP scope, "
        "prioritise features, and sketch a delivery plan.\n\n"
        "Would you like to book a consultation?"
    ),
    "healthcare": (
        "Healthcare projects involve compliance, data security, and integration considerations "
        "that are best discussed in a focused session. "
        "Agicent has worked on HIPAA-compliant platforms and telemedicine products.\n\n"
        "Would you like to schedule a discovery call?"
    ),
    "fintech": (
        "Fintech projects typically involve regulatory, security, and integration complexity "
        "worth discussing directly. Agicent has delivered payment platforms and financial tools.\n\n"
        "Shall we set up a discovery session?"
    ),
}


def get_consultation_offer_message(state: "object") -> str:
    """Pick the most contextually appropriate consultation offer message."""
    try:
        industry = getattr(state, "budget", None) and getattr(state, "timeline", None)
        if industry:
            return CONSULTATION_OFFER_MESSAGES["high_budget"]
        proj_type = getattr(state, "project_type", None)
        ind = getattr(state, "industry", None)
        if ind == "healthcare":
            return CONSULTATION_OFFER_MESSAGES["healthcare"]
        if ind == "fintech":
            return CONSULTATION_OFFER_MESSAGES["fintech"]
        if proj_type in ("mvp", "prototype", "poc"):
            return CONSULTATION_OFFER_MESSAGES["mvp"]
    except Exception:
        pass
    return CONSULTATION_OFFER_MESSAGES["default"]
