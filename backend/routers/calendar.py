"""
routers/calendar.py
────────────────────
Google Calendar booking endpoints for the Agicent consultant agent.

Endpoints:
  GET  /api/calendar/status         — is calendar configured?
  GET  /api/calendar/slots          — available slots (next 7 days)
  POST /api/calendar/book           — create event + send invite

All endpoints degrade gracefully when credentials are not set.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from filelock import FileLock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from config import BASE_DIR
from services.consultant_service import consultant_repo
from services.booking_service import booking_repo
from models import Booking, Consultant

router = APIRouter(prefix="/api/calendar", tags=["calendar"])



# ── Request / Response schemas ─────────────────────────────────────────────

class CalendarStatusResponse(BaseModel):
    configured: bool
    message: str


class CalendarSlotsResponse(BaseModel):
    slots: list[dict]
    timezone: str


class BookingRequest(BaseModel):
    start_iso: str
    end_iso: str
    attendee_email: str
    attendee_name: str
    company: Optional[str] = None
    topic_summary: Optional[str] = None


class BookingResponse(BaseModel):
    ok:           bool
    event_id:     Optional[str] = None
    html_link:    Optional[str] = None
    attendee_link: Optional[str] = None
    meet_link:    Optional[str] = None
    summary:      Optional[str] = None
    start:        Optional[str] = None
    end:          Optional[str] = None
    error:        Optional[str] = None
    booking_id:   Optional[str] = None
    consultant_name: Optional[str] = None



# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status():
    """Check whether Google Calendar integration is configured."""
    try:
        from services.calendar_service import GoogleCalendarService
        svc = GoogleCalendarService()
        ok  = svc.is_configured()
        return CalendarStatusResponse(
            configured=ok,
            message="Calendar integration active." if ok
                    else "Calendar not configured. Set GOOGLE_CALENDAR_CREDENTIALS_JSON.",
        )
    except Exception as e:
        return CalendarStatusResponse(configured=False, message=str(e))


@router.get("/slots", response_model=CalendarSlotsResponse)
async def get_slots(days_ahead: int = 7):
    """Return available 45-minute meeting slots over the next `days_ahead` days."""
    try:
        from services.calendar_service import (
            GoogleCalendarService,
            CalendarNotConfiguredError,
        )
        from config import MEETING_TIMEZONE

        svc   = GoogleCalendarService()
        slots = svc.get_available_slots(days_ahead=max(1, min(days_ahead, 30)))
        return CalendarSlotsResponse(slots=slots, timezone=MEETING_TIMEZONE)

    except Exception as e:
        # Raised as CalendarNotConfiguredError or CalendarBookingError — both return 503
        raise HTTPException(
            status_code=503,
            detail=f"Calendar unavailable: {str(e)}",
        )


def _get_next_consultant_round_robin(available_consultants: list[Consultant]) -> Consultant:
    """Perform round-robin selection from available consultants."""
    if not available_consultants:
        raise ValueError("No consultants available.")
    
    if len(available_consultants) == 1:
        return available_consultants[0]

    all_active = sorted(
        [c for c in consultant_repo.list_all() if c.active],
        key=lambda x: x.id
    )
    if not all_active:
        return available_consultants[0]

    # Load round-robin state
    from database import SessionLocal, DBSchedulingState
    db = SessionLocal()
    last_assigned_id = None
    try:
        state_record = db.query(DBSchedulingState).first()
        if state_record:
            last_assigned_id = state_record.last_assigned_id
    except Exception:
        pass
    finally:
        db.close()

    # Find the index of the last assigned consultant
    last_idx = -1
    if last_assigned_id:
        for idx, c in enumerate(all_active):
            if c.id == last_assigned_id:
                last_idx = idx
                break

    # We start searching from the next index in the sorted list
    chosen = None
    for offset in range(1, len(all_active) + 1):
        test_idx = (last_idx + offset) % len(all_active)
        test_c = all_active[test_idx]
        if any(av.id == test_c.id for av in available_consultants):
            chosen = test_c
            break

    if not chosen:
        chosen = available_consultants[0]

    # Save state
    db = SessionLocal()
    try:
        state_record = db.query(DBSchedulingState).first()
        if not state_record:
            state_record = DBSchedulingState(last_assigned_id=chosen.id)
            db.add(state_record)
        else:
            state_record.last_assigned_id = chosen.id
        db.commit()
    except Exception as e:
        print(f"[RoundRobin] Failed to save state: {e}")
        db.rollback()
    finally:
        db.close()

    return chosen


@router.post("/book", response_model=BookingResponse)
async def book_slot(req: BookingRequest):
    """
    Create a Google Calendar event and send an invitation email to the attendee.
    Assigns a consultant automatically via round-robin.
    """
    if not req.attendee_email or "@" not in req.attendee_email:
        raise HTTPException(status_code=422, detail="Valid attendee_email is required.")
    if not req.attendee_name.strip():
        raise HTTPException(status_code=422, detail="attendee_name is required.")
    if not req.start_iso or not req.end_iso:
        raise HTTPException(status_code=422, detail="start_iso and end_iso are required.")

    try:
        from services.calendar_service import (
            GoogleCalendarService,
            CalendarNotConfiguredError,
            CalendarBookingError,
        )

        # 1. Parse dates to UTC
        try:
            start_dt = datetime.fromisoformat(req.start_iso.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(req.end_iso.replace("Z", "+00:00"))
        except Exception as e:
            return BookingResponse(ok=False, error=f"Invalid date format: {e}")

        # 2. Get available consultants
        svc = GoogleCalendarService()
        available_consultants = svc.get_available_consultants(start_dt, end_dt)
        if not available_consultants:
            return BookingResponse(ok=False, error="No consultants available at this time slot.")

        # 3. Round-robin assignment
        assigned_consultant = _get_next_consultant_round_robin(available_consultants)

        # 4. Create calendar event on the dedicated Discovery Calls calendar
        #    (consultant.calendar_id is used only for availability freebusy queries)
        booking_cal_id = svc.get_booking_calendar_id()
        event = svc.create_event(
            calendar_id=booking_cal_id,
            start_iso=req.start_iso,
            end_iso=req.end_iso,
            attendee_email=req.attendee_email,
            attendee_name=req.attendee_name.strip(),
            topic_summary=(req.topic_summary or "").strip(),
        )

        # 5. Persist booking locally
        booking_id = "bk_" + uuid.uuid4().hex[:18]
        new_booking = Booking(
            booking_id=booking_id,
            consultant_id=assigned_consultant.id,
            attendee_name=req.attendee_name.strip(),
            attendee_email=req.attendee_email.strip(),
            company=req.company.strip() if req.company else None,
            topic_summary=(req.topic_summary or "").strip() or None,
            start_iso=req.start_iso,
            end_iso=req.end_iso,
            event_id=event.event_id,
            html_link=event.html_link,
            attendee_link=event.attendee_link,
            meet_link=event.meet_link,
            status="scheduled",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        booking_repo.create(new_booking)

        return BookingResponse(
            ok           = True,
            event_id     = event.event_id,
            html_link    = event.html_link,
            attendee_link= event.attendee_link,
            meet_link    = event.meet_link,
            summary      = event.summary,
            start        = event.start,
            end          = event.end,
            booking_id   = booking_id,
            consultant_name = assigned_consultant.name,
        )

    except Exception as e:
        return BookingResponse(ok=False, error=str(e))


@router.post("/bookings/{id}/cancel")
async def cancel_booking(id: str):
    """
    Cancel an existing booking, delete Google Calendar event, and update DB.
    Does not require admin token since it's used directly in the reschedule/cancel flow by attendees.
    """
    booking = booking_repo.get_by_id(id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status == "cancelled":
        return {"ok": True, "message": "Booking is already cancelled."}

    # Delete calendar event from the dedicated Discovery Calls calendar
    try:
        from services.calendar_service import GoogleCalendarService
        cal_svc = GoogleCalendarService()
        booking_cal_id = cal_svc.get_booking_calendar_id()
        cal_svc.delete_event(booking_cal_id, booking.event_id)
    except Exception as e:
        print(f"[CalendarRouter] Event delete failed during cancellation: {e}")

    booking.status = "cancelled"
    booking_repo.update(id, booking)
    return {"ok": True}


