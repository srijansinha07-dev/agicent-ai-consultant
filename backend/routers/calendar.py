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
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

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
    ok:         bool
    event_id:   Optional[str]   = None
    html_link:  Optional[str]   = None
    summary:    Optional[str]   = None
    start:      Optional[str]   = None
    end:        Optional[str]   = None
    error:      Optional[str]   = None


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


@router.post("/book", response_model=BookingResponse)
async def book_slot(req: BookingRequest):
    """
    Create a Google Calendar event and send an invitation email to the attendee.
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

        svc   = GoogleCalendarService()
        event = svc.create_event(
            start_iso      = req.start_iso,
            end_iso        = req.end_iso,
            attendee_email = req.attendee_email,
            attendee_name  = req.attendee_name.strip(),
            topic_summary  = (req.topic_summary or "").strip(),
        )

        return BookingResponse(
            ok        = True,
            event_id  = event.event_id,
            html_link = event.html_link,
            summary   = event.summary,
            start     = event.start,
            end       = event.end,
        )

    except Exception as e:
        return BookingResponse(ok=False, error=str(e))
