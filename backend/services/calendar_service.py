"""
services/calendar_service.py
──────────────────────────────
Google Calendar integration for the Agicent consultant booking flow.

Implementation is credential-ready but not credential-dependent:
  - If credentials are configured  → full booking workflow available
  - If credentials are absent      → CalendarNotConfiguredError is raised and
                                     the agent falls back to the consultation form

Auth modes (in priority order):
  1. GOOGLE_CALENDAR_CREDENTIALS_JSON env var (base64-encoded service account JSON)
     → best for Railway/Render deployments; no files needed
  2. GOOGLE_CLIENT_SECRETS_FILE + GOOGLE_OAUTH_TOKEN_FILE
     → standard OAuth2 desktop flow; token refreshed automatically

Setup checklist (run once, then set env vars):
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Google Cloud Console → Enable Google Calendar API        │
  │ 2. Create Service Account → download JSON key               │
  │    base64-encode it: base64 -w0 key.json                    │
  │    Set env: GOOGLE_CALENDAR_CREDENTIALS_JSON=<base64>       │
  │ 3. Share your Google Calendar with the service account email │
  │    Set env: GOOGLE_CALENDAR_ID=team@agicent.com             │
  │ 4. Optional settings:                                        │
  │    MEETING_DURATION_MINUTES=45                               │
  │    MEETING_TIMEZONE=America/New_York                         │
  └─────────────────────────────────────────────────────────────┘

  OR (user OAuth flow):
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. Create OAuth 2.0 Client ID (Desktop app)                 │
  │ 2. Download credentials.json → set GOOGLE_CLIENT_SECRETS_FILE│
  │ 3. Run once: python -m services.calendar_service --auth     │
  │ 4. Token saved to GOOGLE_OAUTH_TOKEN_FILE                   │
  └─────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from config import (
    GOOGLE_CALENDAR_CREDENTIALS_JSON,
    GOOGLE_CALENDAR_ID,
    GOOGLE_CLIENT_SECRETS_FILE,
    GOOGLE_OAUTH_TOKEN_FILE,
    MEETING_DURATION_MINUTES,
    MEETING_TIMEZONE,
)


# ── Exceptions ─────────────────────────────────────────────────────────────

class CalendarNotConfiguredError(Exception):
    """Raised when no Google Calendar credentials are available."""


class CalendarBookingError(Exception):
    """Raised when event creation fails."""


# ── Data types ─────────────────────────────────────────────────────────────

class CalendarSlot:
    def __init__(self, start: datetime, end: datetime):
        self.start   = start
        self.end     = end
        self.display = self._fmt()

    def _fmt(self) -> str:
        tz = ZoneInfo(MEETING_TIMEZONE)
        local = self.start.astimezone(tz)
        return (
            f"{local.strftime('%A')}, "
            f"{local.strftime('%B')} {local.day} at "
            f"{local.strftime('%I').lstrip('0')}:{local.strftime('%M')} "
            f"{local.strftime('%p')} "
            f"{local.strftime('%Z')}"
        )

    def to_dict(self) -> dict:
        return {
            "start":   self.start.isoformat(),
            "end":     self.end.isoformat(),
            "display": self.display,
        }


class CalendarEvent:
    def __init__(self, event_id: str, html_link: str, summary: str,
                 start: str, end: str):
        self.event_id  = event_id
        self.html_link = html_link
        self.summary   = summary
        self.start     = start
        self.end       = end

    def to_dict(self) -> dict:
        return {
            "event_id":  self.event_id,
            "html_link": self.html_link,
            "summary":   self.summary,
            "start":     self.start,
            "end":       self.end,
        }


# ── Service class ──────────────────────────────────────────────────────────

class GoogleCalendarService:
    """
    Thin wrapper around the Google Calendar API.
    Builds and caches credentials on first use.
    """

    def __init__(self):
        self._service = None  # lazy init

    # ── Credentials ──────────────────────────────────────────────────────

    def _get_service(self):
        """Build and cache the Google Calendar API service object."""
        if self._service is not None:
            return self._service

        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise CalendarNotConfiguredError(
                "google-api-python-client is not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        creds = self._load_credentials()
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _load_credentials(self):
        """
        Try credential sources in priority order:
        1. GOOGLE_CALENDAR_CREDENTIALS_JSON env var (base64 service account)
        2. GOOGLE_CLIENT_SECRETS_FILE + GOOGLE_OAUTH_TOKEN_FILE (OAuth2)
        """
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        SCOPES = ["https://www.googleapis.com/auth/calendar"]

        # ── Mode 1: Service account via env var ──────────────────────────
        if GOOGLE_CALENDAR_CREDENTIALS_JSON:
            try:
                raw = base64.b64decode(GOOGLE_CALENDAR_CREDENTIALS_JSON).decode()
                info = json.loads(raw)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
                return creds
            except Exception as e:
                raise CalendarNotConfiguredError(
                    f"Failed to load service account from GOOGLE_CALENDAR_CREDENTIALS_JSON: {e}"
                )

        # ── Mode 2: Service account via file ─────────────────────────────
        sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        if sa_file and os.path.exists(sa_file):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    sa_file, scopes=SCOPES
                )
                return creds
            except Exception as e:
                raise CalendarNotConfiguredError(
                    f"Failed to load service account from file {sa_file}: {e}"
                )

        # ── Mode 3: OAuth2 token file ──────────────────────────────────
        token_file   = GOOGLE_OAUTH_TOKEN_FILE
        secrets_file = GOOGLE_CLIENT_SECRETS_FILE

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_token(creds, token_file)
                return creds
            except Exception as e:
                raise CalendarNotConfiguredError(
                    f"OAuth2 token refresh failed: {e}. Run the auth flow again."
                )

        # No credentials found at all
        if not os.path.exists(secrets_file):
            raise CalendarNotConfiguredError(
                "No Google Calendar credentials found. "
                "Set GOOGLE_CALENDAR_CREDENTIALS_JSON (service account) or "
                f"provide {secrets_file} for OAuth2 flow. "
                "See services/calendar_service.py for setup instructions."
            )

        # Need to run OAuth2 flow interactively
        raise CalendarNotConfiguredError(
            f"OAuth2 token not found at {token_file}. "
            "Run: python -m services.calendar_service --auth"
        )

    # ── Public API ────────────────────────────────────────────────────────

    def get_available_slots(self, days_ahead: int = 7) -> list[dict]:
        """
        Return available 45-minute slots over the next `days_ahead` days.
        Checks existing events and returns gaps in working hours (9am-5pm local).
        """
        service = self._get_service()
        tz      = ZoneInfo(MEETING_TIMEZONE)
        now     = datetime.now(timezone.utc)
        end_dt  = now + timedelta(days=days_ahead)

        # Fetch existing events in the window
        try:
            events_result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=now.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            existing = events_result.get("items", [])
        except Exception as e:
            raise CalendarBookingError(f"Failed to fetch events: {e}")

        busy_blocks = _parse_busy_blocks(existing)
        slots       = _generate_candidate_slots(now, days_ahead, tz)
        available   = [s for s in slots if not _overlaps_any(s, busy_blocks)]
        return [s.to_dict() for s in available[:8]]

    def create_event(
        self,
        *,
        start_iso: str,
        end_iso: str,
        attendee_email: str,
        attendee_name: str,
        topic_summary: str = "",
        organiser_name: str = "Agicent Team",
    ) -> CalendarEvent:
        """
        Create a calendar event and send an invitation to the attendee.
        """
        service  = self._get_service()
        duration = MEETING_DURATION_MINUTES
        summary  = f"Agicent Discovery Call — {attendee_name}"
        if topic_summary:
            summary += f" ({topic_summary[:60]})"

        body = {
            "summary":     summary,
            "description": (
                f"Discovery call with {attendee_name} ({attendee_email}).\n\n"
                + (f"Project context: {topic_summary}\n\n" if topic_summary else "")
                + "Booked via Agicent AI Consultant."
            ),
            "start": {"dateTime": start_iso, "timeZone": MEETING_TIMEZONE},
            "end":   {"dateTime": end_iso,   "timeZone": MEETING_TIMEZONE},
            "attendees": [
                {"email": attendee_email, "displayName": attendee_name},
            ],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email",  "minutes": 24 * 60},
                    {"method": "popup",  "minutes": 15},
                ],
            },
            "conferenceData": {
                "createRequest": {
                    "requestId":             f"agicent-{attendee_email}-{start_iso}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        try:
            event = service.events().insert(
                calendarId=GOOGLE_CALENDAR_ID,
                body=body,
                sendUpdates="all",
                conferenceDataVersion=1,
            ).execute()
        except Exception as e:
            raise CalendarBookingError(f"Failed to create event: {e}")

        return CalendarEvent(
            event_id  = event.get("id", ""),
            html_link = event.get("htmlLink", ""),
            summary   = event.get("summary", summary),
            start     = start_iso,
            end       = end_iso,
        )

    def list_upcoming_events(self, max_results: int = 10) -> list[dict]:
        """Return the next N events on the calendar."""
        service = self._get_service()
        now     = datetime.now(timezone.utc).isoformat()
        try:
            result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return result.get("items", [])
        except Exception as e:
            raise CalendarBookingError(f"Failed to list events: {e}")

    def is_configured(self) -> bool:
        """Check whether credentials are available without raising."""
        try:
            self._get_service()
            return True
        except CalendarNotConfiguredError:
            return False
        except Exception:
            return False


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_busy_blocks(events: list[dict]) -> list[tuple[datetime, datetime]]:
    """Extract (start, end) datetime pairs from Google Calendar event list."""
    blocks = []
    for ev in events:
        s = ev.get("start", {})
        e = ev.get("end", {})
        try:
            start = datetime.fromisoformat(s.get("dateTime") or s.get("date", ""))
            end   = datetime.fromisoformat(e.get("dateTime") or e.get("date", ""))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            blocks.append((start, end))
        except Exception:
            continue
    return blocks


def _generate_candidate_slots(
    from_dt: datetime,
    days: int,
    tz: ZoneInfo,
) -> list[CalendarSlot]:
    """
    Generate 45-minute slot candidates on weekdays between 9am and 5pm local time.
    """
    duration = timedelta(minutes=MEETING_DURATION_MINUTES)
    slots    = []
    day      = from_dt.astimezone(tz).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    for _ in range(days):
        day += timedelta(days=1)
        if day.weekday() >= 5:  # skip Sat/Sun
            continue
        # Slots from 9am to 5pm with 30-min gaps
        for hour in range(9, 17):
            for minute in (0, 30):
                slot_start = day.replace(hour=hour, minute=minute, second=0)
                slot_end   = slot_start + duration
                if slot_end.hour > 17:
                    continue
                slots.append(CalendarSlot(
                    start=slot_start.astimezone(timezone.utc),
                    end=slot_end.astimezone(timezone.utc),
                ))

    return slots


def _overlaps_any(
    slot: CalendarSlot,
    busy: list[tuple[datetime, datetime]],
) -> bool:
    """True if slot overlaps with any busy block."""
    for b_start, b_end in busy:
        if slot.start < b_end and slot.end > b_start:
            return True
    return False


def _save_token(creds, path: str) -> None:
    """Persist refreshed OAuth2 token to disk."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(creds.to_json())
    except Exception as e:
        print(f"[Calendar] Warning: could not save token: {e}")


# ── Interactive auth flow (run once: python -m services.calendar_service --auth) ──

def _run_auth_flow() -> None:
    """Interactive OAuth2 first-time authorisation."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES       = ["https://www.googleapis.com/auth/calendar"]
    secrets_file = GOOGLE_CLIENT_SECRETS_FILE
    token_file   = GOOGLE_OAUTH_TOKEN_FILE

    if not os.path.exists(secrets_file):
        print(f"ERROR: {secrets_file} not found. Download from Google Cloud Console.")
        sys.exit(1)

    flow  = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds, token_file)
    print(f"✅ Token saved to {token_file}")


if __name__ == "__main__":
    if "--auth" in sys.argv:
        _run_auth_flow()
    else:
        # Quick smoke test
        svc = GoogleCalendarService()
        if svc.is_configured():
            print("✅ Calendar configured")
            slots = svc.get_available_slots()
            for s in slots[:3]:
                print(" •", s["display"])
        else:
            print("⚠️  Calendar not configured — see module docstring for setup steps.")
