"""
test_multi_consultant.py
────────────────────────
Unit tests for multi-consultant availability, leave/vacation filtering, and round-robin scheduler.
Run from backend/:
    python test_multi_consultant.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Force database to be SQLite in-memory or a temporary file for tests
os.environ["DATABASE_URL"] = "sqlite:///test_temp.db"

from database import init_db, SessionLocal, DBConsultant, DBBooking, DBSchedulingState
from models import Consultant, ConsultantWorkingHours, ConsultantLeave
from services.calendar_service import _is_consultant_available
from routers.calendar import _get_next_consultant_round_robin
from services.consultant_service import consultant_repo


def test_is_consultant_available():
    print("Testing consultant availability logic...")

    # Define standard Mon-Fri 10:00 - 19:00 IST working hours
    wh = ConsultantWorkingHours(
        start="10:00",
        end="19:00",
        days=[0, 1, 2, 3, 4]  # Mon-Fri
    )

    # 1. Active consultant test
    c = Consultant(
        id="test_c",
        name="Test Consultant",
        email="test@company.com",
        active=True,
        calendar_id="test@company.com",
        working_hours=wh,
        leaves=[],
        unavailabilities=[]
    )

    # Slot: Tuesday, 11:00 AM - 11:45 AM IST (in working hours)
    # UTC equivalent (IST is UTC+5:30): 05:30 AM - 06:15 AM UTC
    slot_start = datetime(2026, 6, 9, 5, 30, tzinfo=timezone.utc)
    slot_end = datetime(2026, 6, 9, 6, 15, tzinfo=timezone.utc)
    busy = []

    assert _is_consultant_available(c, slot_start, slot_end, busy) == True, "Active consultant should be available"

    # 2. Inactive consultant test
    c.active = False
    assert _is_consultant_available(c, slot_start, slot_end, busy) == False, "Inactive consultant should not be available"
    c.active = True

    # 3. Off-hours test (Weekend slot: Saturday, 11:00 AM IST)
    slot_weekend_start = datetime(2026, 6, 13, 5, 30, tzinfo=timezone.utc)
    slot_weekend_end = datetime(2026, 6, 13, 6, 15, tzinfo=timezone.utc)
    assert _is_consultant_available(c, slot_weekend_start, slot_weekend_end, busy) == False, "Weekend slot should be unavailable"

    # 4. Off-hours time test (Tuesday, 8:00 PM IST)
    slot_night_start = datetime(2026, 6, 9, 14, 30, tzinfo=timezone.utc)
    slot_night_end = datetime(2026, 6, 9, 15, 15, tzinfo=timezone.utc)
    assert _is_consultant_available(c, slot_night_start, slot_night_end, busy) == False, "Night slot should be unavailable"

    # 5. Overlapping Google Calendar event test
    busy_events = [
        (datetime(2026, 6, 9, 5, 0, tzinfo=timezone.utc), datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc))
    ]
    assert _is_consultant_available(c, slot_start, slot_end, busy_events) == False, "Overlapping busy block should block availability"

    # 6. Overlapping leave test
    c.leaves = [
        ConsultantLeave(
            start="2026-06-09T00:00:00+05:30",
            end="2026-06-09T23:59:59+05:30",
            description="Sick Leave"
        )
    ]
    assert _is_consultant_available(c, slot_start, slot_end, []) == False, "Slot overlapping leave should be blocked"

    print("[OK] Availability tests passed!")



def test_round_robin_selection():
    print("Testing round-robin scheduling selection...")

    wh = ConsultantWorkingHours(start="10:00", end="19:00", days=[0, 1, 2, 3, 4])
    c1 = Consultant(id="c1", name="Consultant 1", email="c1@company.com", active=True, calendar_id="c1@test.com", working_hours=wh)
    c2 = Consultant(id="c2", name="Consultant 2", email="c2@company.com", active=True, calendar_id="c2@test.com", working_hours=wh)
    c3 = Consultant(id="c3", name="Consultant 3", email="c3@company.com", active=True, calendar_id="c3@test.com", working_hours=wh)

    # Isolate from production data
    init_db()
    db = SessionLocal()
    try:
        db.query(DBConsultant).delete()
        db.query(DBSchedulingState).delete()
        db.commit()
    finally:
        db.close()

    try:
        consultant_repo.create(c1)
        consultant_repo.create(c2)
        consultant_repo.create(c3)

        # Case A: All available
        available = [c1, c2, c3]
        first = _get_next_consultant_round_robin(available)
        assert first in available, "Round robin should pick one of available"

        second = _get_next_consultant_round_robin(available)
        assert second.id != first.id, "Subsequent round-robin assignment should cycle to next consultant"

        third = _get_next_consultant_round_robin(available)
        assert third.id != second.id and third.id != first.id, "Should cycle to third consultant"

        fourth = _get_next_consultant_round_robin(available)
        assert fourth.id == first.id, "Round robin should wrap around to first choice"

        # Case B: Only C2 and C3 available (C1 is busy)
        available_subset = [c2, c3]
        # State should automatically skip C1 if it's not available
        next_up = _get_next_consultant_round_robin(available_subset)
        assert next_up.id in ["c2", "c3"], "Should only assign available subset"

        print("[OK] Round robin tests passed!")
    finally:
        db = SessionLocal()
        try:
            db.query(DBConsultant).delete()
            db.query(DBSchedulingState).delete()
            db.commit()
        finally:
            db.close()


def test_hourly_slots_and_capacity():
    print("Testing hourly slot generation and capacity-awareness...")
    
    # 1. Test slot generation (only hourly slots, no half-hour slots, 10 AM - 7 PM, excluding 1 PM & 2 PM)
    from services.calendar_service import _generate_candidate_slots, GoogleCalendarService
    from services.booking_service import booking_repo
    from models import Booking
    
    tz = ZoneInfo("Asia/Kolkata")
    # A Monday
    from_dt = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    slots = _generate_candidate_slots(from_dt, days=5, tz=tz)
    
    # All slots should start at minute 0 and have a duration of 1 hour (60 minutes)
    for s in slots:
        start_local = s.start.astimezone(tz)
        end_local = s.end.astimezone(tz)
        assert start_local.minute == 0, f"Slot start time should be hourly (minute 0): {start_local}"
        assert end_local.minute == 0, f"Slot end time should be hourly (minute 0): {end_local}"
        assert (s.end - s.start).total_seconds() == 3600, f"Slot duration should be exactly 1 hour: {s.start} to {s.end}"
        assert start_local.hour in [10, 11, 12, 15, 16, 17, 18], f"Slot hour {start_local.hour} should be in allowed hours"
        assert start_local.hour not in [13, 14], f"Slot hour should not be in lunch break (13 or 14)"
    
    # 2. Test capacity (exactly 3 bookings per slot, shared calendar ignore freebusy)
    wh = ConsultantWorkingHours(start="10:00", end="19:00", days=[0, 1, 2, 3, 4])
    c1 = Consultant(id="c1", name="Consultant 1", email="c1@company.com", active=True, calendar_id="primary", working_hours=wh)
    c2 = Consultant(id="c2", name="Consultant 2", email="c2@company.com", active=True, calendar_id="primary", working_hours=wh)
    c3 = Consultant(id="c3", name="Consultant 3", email="c3@company.com", active=True, calendar_id="primary", working_hours=wh)
    
    # Isolate consultant and booking data
    init_db()
    db = SessionLocal()
    try:
        db.query(DBConsultant).delete()
        db.query(DBBooking).delete()
        db.commit()
    finally:
        db.close()
        
    try:
        consultant_repo.create(c1)
        consultant_repo.create(c2)
        consultant_repo.create(c3)
        
        # We check a specific slot: Tuesday, June 9, 2026 at 10:00 AM IST (04:30 AM UTC)
        slot_start = datetime(2026, 6, 9, 4, 30, tzinfo=timezone.utc)
        slot_end = datetime(2026, 6, 9, 5, 30, tzinfo=timezone.utc)
        
        # Slot should be available initially (0 bookings)
        svc = GoogleCalendarService()
        
        from unittest.mock import patch
        class MockDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return from_dt

        def get_capacity(start_dt):
            with patch("services.calendar_service.datetime", MockDatetime):
                slots_data = svc.get_available_slots(days_ahead=7)
            for s in slots_data:
                s_dt = datetime.fromisoformat(s["start"].replace("Z", "+00:00"))
                if s_dt == start_dt:
                    return s["remaining_capacity"]
            return None

        available_c = svc.get_available_consultants(slot_start, slot_end)
        assert len(available_c) == 3, f"Expected 3 available consultants, got {len(available_c)}"
        assert get_capacity(slot_start) == 3, f"Expected slot remaining capacity to be 3, got {get_capacity(slot_start)}"
        
        # Add 1 booking for c1
        bk1 = Booking(
            booking_id="bk1", consultant_id="c1", attendee_name="Guest 1", attendee_email="g1@test.com",
            start_iso=slot_start.isoformat(), end_iso=slot_end.isoformat(), status="scheduled", created_at="2026-06-09T00:00:00Z",
            event_id="dummy1", html_link="http://dummy"
        )
        booking_repo.create(bk1)
        
        # Slot should still be available (2 consultants left)
        available_c = svc.get_available_consultants(slot_start, slot_end)
        assert len(available_c) == 2, f"Expected 2 available consultants, got {len(available_c)}"
        assert "c1" not in [c.id for c in available_c], "Consultant c1 should be busy"
        assert get_capacity(slot_start) == 2, f"Expected slot remaining capacity to be 2, got {get_capacity(slot_start)}"
        
        # Add 2nd booking for c2
        bk2 = Booking(
            booking_id="bk2", consultant_id="c2", attendee_name="Guest 2", attendee_email="g2@test.com",
            start_iso=slot_start.isoformat(), end_iso=slot_end.isoformat(), status="scheduled", created_at="2026-06-09T00:00:00Z",
            event_id="dummy2", html_link="http://dummy"
        )
        booking_repo.create(bk2)
        
        # Slot should still be available (1 consultant left)
        available_c = svc.get_available_consultants(slot_start, slot_end)
        assert len(available_c) == 1, f"Expected 1 available consultant, got {len(available_c)}"
        assert "c3" in [c.id for c in available_c], "Consultant c3 should be the only one available"
        assert get_capacity(slot_start) == 1, f"Expected slot remaining capacity to be 1, got {get_capacity(slot_start)}"
        
        # Add 3rd booking for c3
        bk3 = Booking(
            booking_id="bk3", consultant_id="c3", attendee_name="Guest 3", attendee_email="g3@test.com",
            start_iso=slot_start.isoformat(), end_iso=slot_end.isoformat(), status="scheduled", created_at="2026-06-09T00:00:00Z",
            event_id="dummy3", html_link="http://dummy"
        )
        booking_repo.create(bk3)
        
        # Slot should now be unavailable (0 consultants left)
        available_c = svc.get_available_consultants(slot_start, slot_end)
        assert len(available_c) == 0, f"Expected 0 available consultants, got {len(available_c)}"
        assert get_capacity(slot_start) == 0, f"Expected slot remaining capacity to be 0, got {get_capacity(slot_start)}"
        
        # Test cancel_booking route
        import asyncio
        from routers.calendar import cancel_booking
        
        res = asyncio.run(cancel_booking("bk1"))
        assert res["ok"] == True
        assert booking_repo.get_by_id("bk1").status == "cancelled"
        
        # Capacity should go up to 1 after cancelling 1 booking
        assert get_capacity(slot_start) == 1, f"Expected slot remaining capacity to be 1 after cancel, got {get_capacity(slot_start)}"
        
        print("[OK] Hourly slots and capacity tests passed!")
    finally:
        db = SessionLocal()
        try:
            db.query(DBConsultant).delete()
            db.query(DBBooking).delete()
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    try:
        test_is_consultant_available()
        test_round_robin_selection()
        test_hourly_slots_and_capacity()
        print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        sys.exit(1)
    finally:
        # Clean up temporary DB file
        for p in ["test_temp.db", "test_temp.db-journal"]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


