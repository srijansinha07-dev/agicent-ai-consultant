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
from services.consultant_service import consultant_repo
from services.booking_service import booking_repo
from models import Consultant


def generate_event_url(event_id: str, calendar_id: str) -> str:
    """Helper to construct deep guest-accessible Google Calendar event URL."""
    eid_clean = event_id.split("@")[0]
    cal_clean = calendar_id.replace("@group.calendar.google.com", "@g")
    combined = f"{eid_clean} {cal_clean}"
    encoded = base64.b64encode(combined.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"https://www.google.com/calendar/event?eid={encoded}"


def extract_calendar_id_from_link(html_link: str) -> Optional[str]:
    """Extract and decode calendar ID from a base64 encoded Google Calendar eid link."""
    if not html_link:
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(html_link)
        qs = parse_qs(parsed.query)
        eid = qs.get("eid", [None])[0]
        if eid:
            # Add padding if needed
            missing_padding = len(eid) % 4
            if missing_padding:
                eid += '=' * (4 - missing_padding)
            decoded = base64.b64decode(eid).decode("utf-8")
            parts = decoded.split(" ")
            if len(parts) >= 2:
                cal_id = parts[1]
                if cal_id.endswith("@g"):
                    cal_id = cal_id[:-2] + "@group.calendar.google.com"
                return cal_id
    except Exception as e:
        print(f"[Calendar] Failed to extract calendar ID from link {html_link}: {e}")
    return None



# ── Exceptions ─────────────────────────────────────────────────────────────

class CalendarNotConfiguredError(Exception):
    """Raised when no Google Calendar credentials are available."""


class CalendarBookingError(Exception):
    """Raised when event creation fails."""


# ── Data types ─────────────────────────────────────────────────────────────

class CalendarSlot:
    def __init__(self, start: datetime, end: datetime, remaining_capacity: int = 0):
        self.start              = start
        self.end                = end
        self.display            = self._fmt()
        self.remaining_capacity = remaining_capacity

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
            "remaining_capacity": self.remaining_capacity,
        }


# Known ID for "Agicent Discovery Calls" calendar (static fallback)
_DISCOVERY_CALENDAR_NAME    = "Agicent Discovery Calls"
_STATIC_FALLBACK_CALENDAR_ID = (
    "c_b90ef9abb2fc5e55d049cebca203851ca71d666d1ccd62225bce86e612ccc12e"
    "@group.calendar.google.com"
)


class CalendarEvent:
    def __init__(
        self,
        event_id:      str,
        html_link:     str,
        summary:       str,
        start:         str,
        end:           str,
        attendee_link: str = "",
        meet_link:     str = "",
    ):
        self.event_id      = event_id
        self.html_link     = html_link
        self.attendee_link = attendee_link
        self.meet_link     = meet_link
        self.summary       = summary
        self.start         = start
        self.end           = end

    def to_dict(self) -> dict:
        return {
            "event_id":      self.event_id,
            "html_link":     self.html_link,
            "attendee_link": self.attendee_link,
            "meet_link":     self.meet_link,
            "summary":       self.summary,
            "start":         self.start,
            "end":           self.end,
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
        print("GOOGLE_CALENDAR_CREDENTIALS_JSON exists:", bool(GOOGLE_CALENDAR_CREDENTIALS_JSON))
        print("GOOGLE_OAUTH_CREDENTIALS_JSON exists:", bool(os.getenv("GOOGLE_OAUTH_CREDENTIALS_JSON")))
        print("GOOGLE_OAUTH_TOKEN_JSON exists:", bool(os.getenv("GOOGLE_OAUTH_TOKEN_JSON")))
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        SCOPES = ["https://www.googleapis.com/auth/calendar"]

        # ── Mode 1: Service account via env var ──────────────────────────
        if GOOGLE_CALENDAR_CREDENTIALS_JSON:

            oauth_json = os.getenv("GOOGLE_OAUTH_CREDENTIALS_JSON", "")
            token_json = os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "")

        if oauth_json and token_json:
            from google.oauth2.credentials import Credentials

            creds_info = json.loads(
                base64.b64decode(token_json).decode()
            )

            creds = Credentials.from_authorized_user_info(
                creds_info,
                SCOPES
            )
            return creds
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

    def get_freebusy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, list[tuple[datetime, datetime]]]:
        """
        Query freebusy status for multiple calendar IDs.
        Returns a dict mapping calendar_id to a list of busy (start, end) datetime blocks in UTC.
        """
        if not calendar_ids:
            return {}
        try:
            service = self._get_service()
            body = {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": cid} for cid in calendar_ids]
            }
            res = service.freebusy().query(body=body).execute()
            calendars = res.get("calendars", {})

            busy_data = {}
            for cid in calendar_ids:
                cal_res = calendars.get(cid, {})
                busy_list = cal_res.get("busy", [])
                blocks = []
                for b in busy_list:
                    try:
                        b_start = datetime.fromisoformat(b.get("start").replace("Z", "+00:00"))
                        b_end = datetime.fromisoformat(b.get("end").replace("Z", "+00:00"))
                        blocks.append((b_start, b_end))
                    except Exception:
                        continue
                busy_data[cid] = blocks
            return busy_data
        except Exception as e:
            print(f"[Calendar] Freebusy query failed: {e}")
            return {cid: [] for cid in calendar_ids}

    def get_available_consultants(self, start: datetime, end: datetime) -> list[Consultant]:
        """
        Query availability and return list of active consultants free during the start/end window.
        """
        active_consultants = [c for c in consultant_repo.list_all() if c.active]
        if not active_consultants:
            return []
        
        shared_cal_id = self.get_booking_calendar_id()
        calendar_ids = [
            c.calendar_id for c in active_consultants 
            if c.calendar_id and c.calendar_id != shared_cal_id
        ]
        busy_map = self.get_freebusy(calendar_ids, start, end) if calendar_ids else {}

        available = []
        for consultant in active_consultants:
            consultant_busy = []
            if consultant.calendar_id and consultant.calendar_id != shared_cal_id:
                consultant_busy = busy_map.get(consultant.calendar_id, [])
            if _is_consultant_available(consultant, start, end, consultant_busy):
                available.append(consultant)
        return available

    def get_available_slots(self, days_ahead: int = 7) -> list[dict]:
        """
        Return available hourly slots over the next `days_ahead` days.
        Availability is calculated across all active consultants.
        """
        if not self.is_configured():
            raise CalendarNotConfiguredError("Google Calendar is not configured.")

        # 1. Fetch active consultants
        active_consultants = [c for c in consultant_repo.list_all() if c.active]
        if not active_consultants:
            return []

        tz = ZoneInfo(MEETING_TIMEZONE)
        now = datetime.now(timezone.utc)
        end_dt = now + timedelta(days=days_ahead)

        # 2. Get freebusy for active consultants (excluding the shared booking calendar)
        shared_cal_id = self.get_booking_calendar_id()
        calendar_ids = [
            c.calendar_id for c in active_consultants 
            if c.calendar_id and c.calendar_id != shared_cal_id
        ]
        busy_map = self.get_freebusy(calendar_ids, now, end_dt) if calendar_ids else {}

        # 3. Generate and filter slots
        slots = _generate_candidate_slots(now, days_ahead, tz)
        available = []

        for slot in slots:
            available_consultants_count = 0
            # Check how many active consultants are available
            for consultant in active_consultants:
                consultant_busy = []
                if consultant.calendar_id and consultant.calendar_id != shared_cal_id:
                    consultant_busy = busy_map.get(consultant.calendar_id, [])
                if _is_consultant_available(consultant, slot.start, slot.end, consultant_busy):
                    available_consultants_count += 1
            
            slot.remaining_capacity = available_consultants_count
            available.append(slot)

        return [s.to_dict() for s in available]

    def create_event(
        self,
        *,
        calendar_id: str,
        start_iso: str,
        end_iso: str,
        attendee_email: str,
        attendee_name: str,
        topic_summary: str = "",
        organiser_name: str = "Agicent Team",
    ) -> CalendarEvent:
        """
        Create a calendar event on the specified consultant's calendar and invite the attendee.
        """
        service  = self._get_service()
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
                calendarId=calendar_id,
                body=body,
                sendUpdates="all",
                conferenceDataVersion=1,
            ).execute()
        except Exception as e:
            raise CalendarBookingError(f"Failed to create event: {e}")

        # Link preference: prefer htmlLink from the API (organiser view)
        event_id  = event.get("id", "")
        html_link = event.get("htmlLink", "")
        if not html_link:
            html_link = generate_event_url(event_id, calendar_id)

        # Attendee-accessible deep-link (encoded eid format, works for guests)
        attendee_link = generate_event_url(event_id, calendar_id) if event_id else html_link

        # Google Meet link — universally accessible to attendees via video entry point
        meet_link = ""
        conf_data = event.get("conferenceData", {})
        for ep in conf_data.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri", "")
                print(f"[Calendar] Google Meet link extracted: {meet_link}")
                break
        if not meet_link:
            print("[Calendar] Warning: no Meet entryPoint found in conferenceData.")

        return CalendarEvent(
            event_id      = event_id,
            html_link     = html_link,
            attendee_link = attendee_link,
            meet_link     = meet_link,
            summary       = event.get("summary", summary),
            start         = start_iso,
            end           = end_iso,
        )

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Delete an event from Google Calendar."""
        print(f"[Calendar] Attempting to delete event {event_id} from calendar {calendar_id}...")
        service = self._get_service()
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates="all",
            ).execute()
            print(f"[Calendar] Successfully deleted event {event_id} from calendar {calendar_id}.")
        except Exception as e:
            print(f"[Calendar] Failed to delete event {event_id} from calendar {calendar_id}: {e}")

    def list_upcoming_events(self, max_results: int = 10, calendar_id: str = GOOGLE_CALENDAR_ID) -> list[dict]:
        """Return the next N events on the calendar."""
        service = self._get_service()
        now     = datetime.now(timezone.utc).isoformat()
        try:
            result = service.events().list(
                calendarId=calendar_id,
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

    def get_booking_calendar_id(self) -> str:
        """
        Resolve the calendar ID to use when creating discovery call bookings.

        Priority order:
          1. GOOGLE_CALENDAR_ID env var (if set and not 'primary')
          2. Calendar named 'Agicent Discovery Calls' in the account
          3. Static known fallback calendar ID
          4. 'primary'
        """
        # Priority 1: explicit env var
        if GOOGLE_CALENDAR_ID and GOOGLE_CALENDAR_ID not in ("primary", ""):
            print(f"[Calendar] Using GOOGLE_CALENDAR_ID env var: {GOOGLE_CALENDAR_ID}")
            return GOOGLE_CALENDAR_ID

        # Priority 2: search the calendar list by name
        try:
            service = self._get_service()
            cal_list = service.calendarList().list().execute()
            for cal in cal_list.get("items", []):
                if cal.get("summary", "").strip() == _DISCOVERY_CALENDAR_NAME:
                    cid = cal["id"]
                    print(f"[Calendar] Resolved '{_DISCOVERY_CALENDAR_NAME}' → {cid}")
                    return cid
            print(f"[Calendar] '{_DISCOVERY_CALENDAR_NAME}' not found in calendar list.")
        except Exception as e:
            print(f"[Calendar] Warning: calendar list lookup failed: {e}")

        # Priority 3: static fallback
        print(f"[Calendar] Using static fallback calendar ID.")
        return _STATIC_FALLBACK_CALENDAR_ID


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
    Generate slot candidates hourly on IST weekdays.
    Available booking times: 10 AM, 11 AM, 12 PM, 3 PM, 4 PM, 5 PM, 6 PM IST.
    Duration of each slot is 1 hour (60 minutes).
    """
    duration = timedelta(hours=1)
    slots    = []
    day      = from_dt.astimezone(tz).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    for _ in range(days):
        day += timedelta(days=1)
        if day.weekday() >= 5:  # skip Sat/Sun
            continue

        for hour in [10, 11, 12, 15, 16, 17, 18]:
            slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end   = slot_start + duration

            slots.append(CalendarSlot(
                start=slot_start.astimezone(timezone.utc),
                end=slot_end.astimezone(timezone.utc),
            ))

    return slots



def _is_consultant_available(
    consultant: Consultant,
    slot_start: datetime,  # UTC offset-aware
    slot_end: datetime,    # UTC offset-aware
    busy_blocks: list[tuple[datetime, datetime]],
) -> bool:
    """True if the consultant is active and free during the slot start/end range."""
    if not consultant.active:
        return False

    # 1. Check working hours
    # Use timezone specified in working_hours or default MEETING_TIMEZONE
    try:
        tz_name = getattr(consultant.working_hours, "timezone", MEETING_TIMEZONE) or MEETING_TIMEZONE
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(MEETING_TIMEZONE)

    local_start = slot_start.astimezone(tz)
    local_end = slot_end.astimezone(tz)

    # Check weekday
    if local_start.weekday() not in consultant.working_hours.days:
        return False

    # Check start/end time hours
    try:
        sh, sm = map(int, consultant.working_hours.start.split(":"))
        eh, em = map(int, consultant.working_hours.end.split(":"))
        work_start = local_start.replace(hour=sh, minute=sm, second=0, microsecond=0)
        work_end = local_start.replace(hour=eh, minute=em, second=0, microsecond=0)
        if local_start < work_start or local_end > work_end:
            return False
    except Exception:
        # If format parsing fails, fallback to allowing
        pass

    # 2. Check leaves & vacations
    for leave in consultant.leaves:
        try:
            l_start = datetime.fromisoformat(leave.start.replace("Z", "+00:00"))
            l_end = datetime.fromisoformat(leave.end.replace("Z", "+00:00"))
            if slot_start < l_end and slot_end > l_start:
                return False
        except Exception:
            continue

    # 3. Check unavailability periods
    for unavail in consultant.unavailabilities:
        try:
            u_start = datetime.fromisoformat(unavail.start.replace("Z", "+00:00"))
            u_end = datetime.fromisoformat(unavail.end.replace("Z", "+00:00"))
            if slot_start < u_end and slot_end > u_start:
                return False
        except Exception:
            continue

    # 4. Check Google Calendar busy blocks (consultant's personal calendar)
    for b_start, b_end in busy_blocks:
        if slot_start < b_end and slot_end > b_start:
            return False

    # 5. Check locally stored bookings so consultants aren't double-booked
    #    (bookings land on the shared Discovery Calls calendar, not the
    #    consultant's personal calendar, so freebusy alone is insufficient)
    try:
        stored = booking_repo.list_all()
        for bk in stored:
            if bk.consultant_id != consultant.id:
                continue
            if bk.status == "cancelled":
                continue
            try:
                bk_start = datetime.fromisoformat(bk.start_iso.replace("Z", "+00:00"))
                bk_end   = datetime.fromisoformat(bk.end_iso.replace("Z", "+00:00"))
                if slot_start < bk_end and slot_end > bk_start:
                    return False
            except Exception:
                continue
    except Exception as e:
        print(f"[Calendar] Warning: local booking overlap check failed: {e}")

    return True


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
