"""
routers/admin.py
──────────────────
FastAPI router containing all admin panel endpoints.
Protected by admin token validation.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel

from config import CONSULTATION_ADMIN_KEY
from models import (
    Consultant,
    Booking,
    AdminDashboardStats,
    AdminLoginRequest,
    AdminLoginResponse,
)
from services.consultant_service import consultant_repo
from services.booking_service import booking_repo
from services.consultations_service import list_consultations
from services.calendar_service import GoogleCalendarService

# Router configuration
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Token management (in-memory, 24h expiration)
_admin_tokens: dict[str, float] = {}
_TOKEN_TTL = 24 * 3600  # 24 hours


def generate_token() -> str:
    token = "admin_tok_" + uuid.uuid4().hex
    _admin_tokens[token] = time.time() + _TOKEN_TTL
    return token


def is_token_valid(token: str) -> bool:
    if not token:
        return False
    expiry = _admin_tokens.get(token)
    if not expiry:
        return False
    if time.time() > expiry:
        del _admin_tokens[token]
        return False
    return True


# Dependency to verify token
async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    if not x_admin_token or not is_token_valid(x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized or expired admin session.")
    return x_admin_token


# ── Auth Endpoints ─────────────────────────────────────────────────────────

@router.post("/login", response_model=AdminLoginResponse)
async def login(req: AdminLoginRequest):
    expected_key = CONSULTATION_ADMIN_KEY or "agicent_admin"
    if req.key == expected_key:
        token = generate_token()
        return AdminLoginResponse(token=token, ok=True)
    raise HTTPException(status_code=401, detail="Invalid admin key.")


# ── Dashboard & Stats ──────────────────────────────────────────────────────

class ReassignRequest(BaseModel):
    new_consultant_id: str


@router.get("/dashboard", dependencies=[Depends(verify_admin_token)])
async def get_dashboard():
    all_bookings = booking_repo.list_all()
    bookings = [b for b in all_bookings if b.status != "cancelled"]
    consultants = consultant_repo.list_all()
    consultations = list_consultations()

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    today_bookings = []
    upcoming_bookings = []
    
    for b in bookings:
        try:
            b_start = datetime.fromisoformat(b.start_iso.replace("Z", "+00:00"))
            b_day_str = b_start.strftime("%Y-%m-%d")
            
            if b_day_str == today_str:
                today_bookings.append(b)
            elif b_start > now:
                upcoming_bookings.append(b)
        except Exception:
            continue

    active_consultants_count = sum(1 for c in consultants if c.active)

    stats = AdminDashboardStats(
        total_bookings=len(bookings),
        active_consultants=active_consultants_count,
        today_bookings_count=len(today_bookings),
        pending_consultations_count=len(consultations),
    )

    return {
        "stats": stats,
        "today_bookings": today_bookings,
        "upcoming_bookings": upcoming_bookings,
        "consultants": consultants,
    }


# ── Consultants Management ─────────────────────────────────────────────────

@router.get("/consultants", response_model=list[Consultant], dependencies=[Depends(verify_admin_token)])
async def list_consultants_endpoint():
    return consultant_repo.list_all()


@router.post("/consultants", response_model=Consultant, dependencies=[Depends(verify_admin_token)])
async def create_consultant_endpoint(consultant: Consultant):
    try:
        return consultant_repo.create(consultant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/consultants/{id}", response_model=Consultant, dependencies=[Depends(verify_admin_token)])
async def update_consultant_endpoint(id: str, consultant: Consultant):
    updated = consultant_repo.update(id, consultant)
    if not updated:
        raise HTTPException(status_code=404, detail="Consultant not found.")
    return updated


@router.delete("/consultants/{id}", dependencies=[Depends(verify_admin_token)])
async def delete_consultant_endpoint(id: str):
    success = consultant_repo.delete(id)
    if not success:
        raise HTTPException(status_code=404, detail="Consultant not found.")
    return {"ok": True}


# ── Bookings Management ────────────────────────────────────────────────────

@router.get("/bookings", response_model=list[Booking], dependencies=[Depends(verify_admin_token)])
async def list_bookings_endpoint():
    return booking_repo.list_all()


@router.post("/bookings/{id}/reassign", response_model=Booking, dependencies=[Depends(verify_admin_token)])
async def reassign_booking_endpoint(id: str, req: ReassignRequest):
    booking = booking_repo.get_by_id(id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    new_consultant = consultant_repo.get_by_id(req.new_consultant_id)
    if not new_consultant or not new_consultant.active:
        raise HTTPException(status_code=400, detail="Target consultant is invalid or inactive.")

    if booking.consultant_id == req.new_consultant_id:
        return booking  # Already assigned

    # Perform Google Calendar migration on the dedicated Discovery Calls calendar
    cal_svc = GoogleCalendarService()
    booking_cal_id = cal_svc.get_booking_calendar_id()
    
    # 1. Delete old event from booking calendar
    try:
        cal_svc.delete_event(booking_cal_id, booking.event_id)
    except Exception as e:
        print(f"[AdminRouter] Old event delete failed during reassignment: {e}")

    # 2. Create new event on booking calendar
    try:
        new_event = cal_svc.create_event(
            calendar_id=booking_cal_id,
            start_iso=booking.start_iso,
            end_iso=booking.end_iso,
            attendee_email=booking.attendee_email,
            attendee_name=booking.attendee_name,
            topic_summary=booking.topic_summary or "",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to create event on booking calendar: {e}")

    # 3. Update booking record
    booking.consultant_id = new_consultant.id
    booking.event_id = new_event.event_id
    booking.html_link = new_event.html_link
    booking.attendee_link = new_event.attendee_link
    
    updated = booking_repo.update(id, booking)
    return updated


@router.post("/bookings/{id}/cancel", response_model=Booking, dependencies=[Depends(verify_admin_token)])
async def cancel_booking_endpoint(id: str):
    booking = booking_repo.get_by_id(id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status == "cancelled":
        return booking

    # Delete calendar event from the dedicated Discovery Calls calendar
    try:
        cal_svc = GoogleCalendarService()
        booking_cal_id = cal_svc.get_booking_calendar_id()
        cal_svc.delete_event(booking_cal_id, booking.event_id)
    except Exception as e:
        print(f"[AdminRouter] Event delete failed during cancellation: {e}")

    booking.status = "cancelled"
    updated = booking_repo.update(id, booking)
    return updated


@router.post("/bookings/{id}/complete", response_model=Booking, dependencies=[Depends(verify_admin_token)])
async def complete_booking_endpoint(id: str):
    booking = booking_repo.get_by_id(id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    booking.status = "completed"
    updated = booking_repo.update(id, booking)
    return updated


# ── TEMPORARY RECOVERY ENDPOINT ────────────────────────────────────────────

def _run_reindex():
    import os
    print("\n[Recovery] === STARTING PRODUCTION REINDEX ===")
    
    # 1. Railway Safety Guard
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        print("[Recovery] Refusing to run outside Railway")
        return

    # 2. Verify Data File Exists exactly as ingest_website sees it
    from ingest_website import INPUT_FILE
    data_path = os.path.abspath(INPUT_FILE)
    exists = os.path.exists(data_path)
    print(f"[Recovery] Data file exists: {exists}")
    print(f"[Recovery] Resolved path: {data_path}")
    if not exists:
        print(f"[Recovery] FATAL: {INPUT_FILE} is missing.")
        return
    print(f"[Recovery] File size: {os.path.getsize(data_path)} bytes")

    # 3. Load the embedding model FIRST & 4. Run a small test embedding
    print("[Recovery] Loading embedding model...")
    try:
        from services.vectorstore import _embed
        # This natively triggers the Hugging Face download if missing
        test_result = _embed(["hello world"])
        if not test_result or len(test_result[0]) == 0:
            raise ValueError("Embedding result was empty.")
        print("[Recovery] Embedding model loaded successfully")
        print(f"[Recovery] Embedding type: {type(test_result)}")
        print(f"[Recovery] Embedding count: {len(test_result)}")
        print(f"[Recovery] Embedding dimensions: {len(test_result[0])}")
        print("[Recovery] Test embedding generated successfully")
        print("[Recovery] Safe to proceed with deletion")
    except Exception as e:
        print(f"[Recovery] FATAL: Model loading or test embedding failed: {e}")
        print("[Recovery] Aborting recovery before touching DB.")
        return

    # 5. Before Verification
    import chromadb
    from config import CHROMA_PATH
    from chromadb.config import Settings
    
    try:
        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        collections = client.list_collections()
        print(f"[Recovery] BEFORE DELETE total collections: {len(collections)}")
        print(f"[Recovery] BEFORE DELETE collection names: {[c.name for c in collections]}")
        try:
            c = client.get_collection("agicent-website")
            print(f"[Recovery] BEFORE DELETE count={c.count()}")
        except Exception:
            print("[Recovery] BEFORE DELETE count=0 (not found)")
    except Exception as e:
        print(f"[Recovery] Error reading Chroma DB before delete: {e}")
        return

    # 6. Delete the corrupted collection
    print(f"[Recovery] Deleting collection: agicent-website")
    try:
        client.delete_collection("agicent-website")
        print("[Recovery] Collection deleted successfully.")
    except Exception as e:
        print(f"[Recovery] Warning during deletion: {e}")

    # 7. Run the ingestion script
    print("[Recovery] Calling ingest_website()...")
    try:
        from ingest_website import ingest_website
        ingest_website()
        print("[Recovery] ingest_website() completed.")
    except Exception as e:
        print(f"[Recovery] FATAL: Ingestion failed: {e}")
        return

    # 8. After Verification
    try:
        collections = client.list_collections()
        print(f"[Recovery] AFTER INGEST total collections: {len(collections)}")
        print(f"[Recovery] AFTER INGEST collection names: {[c.name for c in collections]}")
        try:
            c = client.get_collection("agicent-website")
            print(f"[Recovery] AFTER INGEST count={c.count()}")
        except Exception:
            print("[Recovery] AFTER INGEST count=0 (not found)")
        print("[Recovery] === REINDEX FINISHED ===")
    except Exception as e:
        print(f"[Recovery] Verification failed: {e}")


@router.post("/reindex-website-recovery", dependencies=[Depends(verify_admin_token)])
async def reindex_website_recovery_endpoint(background_tasks: BackgroundTasks):
    """
    TEMPORARY production recovery endpoint. 
    Deletes the corrupted ChromaDB collection and runs native ingestion.
    """
    background_tasks.add_task(_run_reindex)
    return {
        "ok": True, 
        "message": "Reindex started in background. Monitor Railway logs for progress."
    }
