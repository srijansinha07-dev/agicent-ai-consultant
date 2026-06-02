"""
models.py — Pydantic schemas and internal dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pydantic import BaseModel


# ── Enums ──────────────────────────────────────────────────────────────────

class QueryType(str, Enum):
    PAGE    = "page"
    FORMULA = "formula"
    CONCEPT = "concept"
    EXACT   = "exact"

class IndexStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    READY      = "ready"
    ERROR      = "error"

class ConfidenceLevel(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


# ── Internal dataclasses ───────────────────────────────────────────────────

@dataclass
class Chunk:
    text:            str
    page:            int
    chunk_id:        str
    doc_id:          str
    has_formula:     bool  = False
    section_heading: str   = ""
    score:           float = 0.0
    ocr_sourced:     bool  = False


@dataclass
class RetrievalResult:
    chunks:      list[Chunk]    = field(default_factory=list)
    query_type:  QueryType      = QueryType.CONCEPT
    target_page: Optional[int]  = None


# ── API request / response schemas ────────────────────────────────────────

class ChatRequest(BaseModel):
    doc_id:  str
    query:   str
    history: list[dict] = []

class Source(BaseModel):
    doc_id:      str
    doc_name:    str
    page:        int
    text:        str
    ocr_sourced: bool
    confidence:  ConfidenceLevel
    label:       str = ""
    url:         Optional[str] = None

class ChatResponse(BaseModel):
    answer:     str
    query_type: QueryType
    sources:    list[Source]

class DocumentInfo(BaseModel):
    doc_id:      str
    user_id:     str
    name:        str
    pages:       int
    status:      IndexStatus
    ocr_pages:   int
    chunks:      int
    upload_time: str
    suggestions: list[str] = []

class UploadResponse(BaseModel):
    doc_id:  str
    name:    str
    pages:   int
    status:  IndexStatus

class PagePreviewResponse(BaseModel):
    doc_id:     str
    page:       int
    text:       str
    ocr_used:   bool
    image_b64:  Optional[str] = None  # base64 PNG of the rendered page


# ── Consultation requests (staff handoff) ─────────────────────────────

class ConsultationConversationItem(BaseModel):
    role: str
    content: str


class ConsultationCreateRequest(BaseModel):
    name: str
    email: str
    company: str
    project_description: str
    budget: Optional[str] = None
    timeline: Optional[str] = None
    conversation_history: list[ConsultationConversationItem]
    session_id: Optional[str] = None


class ConsultationCreateResponse(BaseModel):
    ok: bool
    consultation_id: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None


class ConsultationRecord(BaseModel):
    consultation_id: str
    created_at: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    name: str
    email: str
    company: str
    project_description: str
    budget: Optional[str] = None
    timeline: Optional[str] = None

    project_summary: str

    # Stored for staff context; can be omitted later if needed.
    conversation_history: list[ConsultationConversationItem] = []
