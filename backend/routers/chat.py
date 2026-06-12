"""
routers/chat.py
───────────────
/api/chat — answer questions about a document.
Returns structured JSON with answer + sources.

Now powered by a LangGraph multi-node RAG pipeline
(services/langgraph_chat.py).  API contract is unchanged.
"""
from __future__ import annotations

import os

from fastapi import Header
from fastapi import APIRouter, HTTPException

from models import (
    ChatRequest, ChatResponse, ConfidenceLevel,
    IndexStatus, QueryType, Source,
)
from services import docstore

router = APIRouter(prefix="/api/chat", tags=["chat"])
AGENTIC_ROUTER_ENABLED    = os.getenv("AGENTIC_ROUTER_ENABLED", "true").lower() == "true"
CONSULTANT_AGENT_ENABLED = os.getenv("CONSULTANT_AGENT_ENABLED", "true").lower() == "true"


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest,x_user_id: str = Header(...)):
    
    # ── Validate document ─────────────────────────────────────────────────
    info = docstore.get_info(req.doc_id)
    if not info:
        raise HTTPException(404, "Document not found.")
    if info.user_id != x_user_id:
        raise HTTPException(403,"Unauthorized.")
    if info.status != IndexStatus.READY:
        raise HTTPException(400, f"Document is not ready (status: {info.status}).")

    from services.website_support import is_website_doc
    website_doc = is_website_doc(req.doc_id)

    # ── NEW: Consultant Agent (stateful, token-optimised, agentic) ────────
    # Takes priority over all legacy paths for website docs when enabled.
    if website_doc and CONSULTANT_AGENT_ENABLED:
        try:
            from services.consultant_agent import run_consultant_agent

            chunks = docstore.get_chunks(req.doc_id)
            pages  = docstore.get_pages(req.doc_id)

            session_id = req.session_id or x_user_id or "anon"

            result = run_consultant_agent(
                session_id  = session_id,
                query       = req.query,
                history     = req.history,
                doc_id      = req.doc_id,
                chunks_all  = chunks,
                pages_all   = pages,
                doc_info    = info,
                booking_state = req.booking_state,
            )

            answer           = result["answer"]
            query_type       = result["query_type"] or QueryType.CONCEPT
            retrieved_chunks = result["retrieved_chunks"]

            consultation_intent = None
            action = result.get("action")

            if action in ["OFFER_CONSULTATION", "BOOK_CALL"]:
                consultation_intent = "request"

            # Build sources (same logic as below)
            from services.website_support import (
                derive_website_source_label,
                extract_website_metadata,
            )
            sources = []
            for c in retrieved_chunks:
                url, title, heading = extract_website_metadata(c)
                label = derive_website_source_label(url, title, heading)
                if not label.strip():
                    continue
                sources.append(Source(
                    doc_id      = req.doc_id,
                    doc_name    = info.name,
                    page        = c.page,
                    text        = c.text[:400] + ("…" if len(c.text) > 400 else ""),
                    ocr_sourced = c.ocr_sourced,
                    confidence  = _confidence(c.score, c.ocr_sourced),
                    label       = label,
                    url         = url or None,
                ))
            return ChatResponse(
                answer=answer,
                query_type=query_type,
                sources=sources,
                consultationIntent=consultation_intent,
                consultationSummary=result.get("consultationSummary"),
                availableSlots=result.get("availableSlots"),
                budget=result.get("budget"),
                timeline=result.get("timeline"),
            )


        except Exception as e:
            print(f"[Chat Router] Consultant agent failed, falling back: {e}")
            # Fall through to legacy path below

    # ── Legacy: Lightweight intent routing (website consultant mode) ──────
    # Only reached if consultant agent is disabled or raised an exception.
    if website_doc and not CONSULTANT_AGENT_ENABLED:
        try:
            from services.intent_router import (
                classify_intent,
                generate_conversational_reply,
                route_without_retrieval,
            )

            intent = classify_intent(req.query, req.history)
            if route_without_retrieval(intent):
                return ChatResponse(
                    answer=generate_conversational_reply(
                        intent=intent,
                        query=req.query,
                        history=req.history,
                    ),
                    query_type=QueryType.CONCEPT,
                    sources=[],
                )
        except Exception as e:
            print(f"[Chat Router] Intent routing skipped due to error: {e}")

    chunks = docstore.get_chunks(req.doc_id)
    pages  = docstore.get_pages(req.doc_id)

    # ── Run pipeline (feature-gated agentic router with safe fallback) ───
    if AGENTIC_ROUTER_ENABLED:
        try:
            # Lazy import keeps startup memory low.
            from services.agentic_chat import run_agentic_chat

            result = run_agentic_chat(
                doc_id=req.doc_id,
                query=req.query,
                chunks_all=chunks,
                pages_all=pages,
                doc_info=info,
            )
        except Exception as e:
            print(f"[Chat Router] Agentic path failed, falling back to LangGraph: {e}")
            from services.langgraph_chat import run_chat_graph
            result = run_chat_graph(
                doc_id=req.doc_id,
                query=req.query,
                chunks_all=chunks,
                pages_all=pages,
                doc_info=info,
            )
    else:
        # Existing behavior when feature disabled.
        from services.langgraph_chat import run_chat_graph
        result = run_chat_graph(
            doc_id=req.doc_id,
            query=req.query,
            chunks_all=chunks,
            pages_all=pages,
            doc_info=info,
        )

    answer            = result["answer"]
    query_type        = result["query_type"] or QueryType.CONCEPT
    retrieved_chunks  = result["retrieved_chunks"]

    consultation_intent = None

    action = result.get("action")

    if action in ["OFFER_CONSULTATION", "BOOK_CALL"]:
        consultation_intent = "request"

    # ── Build sources ─────────────────────────────────────────────────────
    from services.website_support import (
        derive_website_source_label,
        extract_website_metadata,
    )

    sources = []
    for c in retrieved_chunks:
        label = info.name
        source_url = None
        if website_doc:
            url, title, heading = extract_website_metadata(c)
            label = derive_website_source_label(url, title, heading)
            source_url = url or None
            # Only expose meaningful Agicent resources to the UI
            if not label.strip():
                continue

        sources.append(Source(
            doc_id=req.doc_id,
            doc_name=info.name,
            page=c.page,
            text=c.text[:400] + ("…" if len(c.text) > 400 else ""),
            ocr_sourced=c.ocr_sourced,
            confidence=_confidence(c.score, c.ocr_sourced),
            label=label,
            url=source_url,
        ))

    return ChatResponse(
        answer=answer,
        query_type=query_type,
        sources=sources,
        consultationIntent=consultation_intent,
        consultationSummary=result.get("consultationSummary"),
        availableSlots=result.get("availableSlots")
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _confidence(score: float, ocr_sourced: bool) -> ConfidenceLevel:
    base = score
    if ocr_sourced:
        base -= 0.1   # slight penalty for OCR uncertainty
    if base >= 0.6:
        return ConfidenceLevel.HIGH
    if base >= 0.3:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW

@router.get("/debug/docs")
async def debug_docs():

    docs = {}

    for doc_id in docstore._store.keys():

        info = docstore.get_info(
            doc_id
        )

        docs[doc_id] = {
            "user_id":
                info.user_id
                if info else None,

            "status":
                str(info.status)
                if info else None
        }

    return docs

@router.post("/debug/ingest-website")
async def ingest_website_debug():

    import json
    import uuid

    from services.chunker import (
        chunk_pages
    )

    from services.vectorstore import (
        index_chunks
    )

    INPUT_FILE = (
        "data/cleaned_pages_v2.json"
    )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        website_pages = (
            json.load(f)
        )

    pages = []

    for i, page in enumerate(
        website_pages,
        start=1
    ):

        combined_text = (
            f"{page.get('title', '')}\n\n"
            f"URL: {page.get('url', '')}\n\n"
            f"{' | '.join(page.get('headings', []))}\n\n"
            f"{page.get('content', '')}"
        )

        pages.append(
            {
                "page_num": i,
                "text": combined_text,
                "ocr_used": False,
            }
        )

    doc_id = "agicent_website"
       
  

    docstore.register(
        doc_id=doc_id,
        user_id="website_bot",
        name="Agicent Website",
        pdf_path="website://agicent",
        pages=len(pages),
    )

    chunks = chunk_pages(
        pages,
        doc_id
    )

    docstore.set_pages(
        doc_id,
        pages
    )

    docstore.set_chunks(
        doc_id,
        chunks
    )

    index_chunks(
        doc_id,
        chunks
    )

    print("SKIPPING INDEXING")

    docstore.set_status(
        doc_id,
        IndexStatus.READY
    )

    return {
        "doc_id": doc_id,
        "chunks": len(chunks),
        "status": "READY"
    }
