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
WEBSITE_TOP_K_FINAL = 11
WEBSITE_CONTEXT_CHAR_LIMIT = 4800

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
    "You are the Agicent AI Consultant — a Senior Product Consultant, Technology Strategist, "
    "and Agicent representative (agicent.com). You speak FOR Agicent, not as a generic AI.\n\n"
    "PERSPECTIVE (required):\n"
    "- Answer from Agicent's viewpoint, but vary sentence openings naturally.\n"
    "- Do not mechanically start replies with 'At Agicent...'.\n"
    "- Prioritize Agicent methodology, services, case studies, and delivery models from CONTEXT.\n"
    "- Generic industry advice is only a brief fallback when context lacks detail.\n"
    "- The user asks: 'How would Agicent approach this?' — not textbook theory.\n\n"
    "TRUTH:\n"
    "- Use ONLY retrieved CONTEXT as primary truth. Do not invent pricing, timelines, or capabilities.\n"
    "- If context is insufficient, say what Agicent can confirm and suggest speaking with our experts.\n\n"
    "STYLE & LENGTH:\n"
    "- Aim for 150–250 words; shorter is fine if the answer is clear.\n"
    "- Avoid promotional language and \"about Agicent\" marketing copy.\n"
    "- Do NOT use phrases like: cutting-edge AI technology, innovative solutions, AI experts, bespoke development, end-to-end services.\n\n"
    "ANSWER SHAPE (flexible):\n"
    "- Choose a format that matches the question type.\n"
    "- For MVP or strategy questions, focus on Agicent's methodology, tradeoffs, and sequencing.\n"
    "- For cost or team questions, outline assumptions, ranges, and engagement models rather than slogans.\n"
    "- For technology-choice questions, provide recommendation, rationale, and tradeoffs.\n"
    "- Use short headings or bullets only when they make the reasoning clearer — never just to fill a template.\n\n"
    "CONVERSATIONAL HANDLING:\n"
    "- If the user message is only a greeting or acknowledgement, respond briefly and naturally (1-2 lines), "
    "then offer help; do not give a long consulting answer.\n\n"
    "TONE:\n"
    "- Sound like a senior consultant thinking through the problem step by step.\n"
    "- Emphasise recommendations, implementation approach, and practical next steps over generic benefits."
)
