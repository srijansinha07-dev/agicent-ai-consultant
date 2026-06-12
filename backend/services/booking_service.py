"""
services/booking_service.py
───────────────────────────
Repository and service layer for managing bookings.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from filelock import FileLock
from typing import Optional

from models import Booking
from config import BASE_DIR

BOOKINGS_FILE = BASE_DIR / "data" / "bookings.json"


class BookingRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Booking]:
        """List all bookings."""
        pass

    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        """Get a booking by ID."""
        pass

    @abstractmethod
    def create(self, booking: Booking) -> Booking:
        """Create a new booking."""
        pass

    @abstractmethod
    def update(self, booking_id: str, booking: Booking) -> Optional[Booking]:
        """Update an existing booking."""
        pass

    @abstractmethod
    def delete(self, booking_id: str) -> bool:
        """Delete a booking."""
        pass


class JSONBookingRepository(BookingRepository):
    """
    JSON file implementation of the BookingRepository.
    Uses file lock for safety.
    """

    def __init__(self, filepath: Path = BOOKINGS_FILE):
        self.filepath = filepath
        self.lock_path = str(filepath) + ".lock"
        self.filepath.parent.mkdir(exist_ok=True)

    def _load_all(self) -> list[Booking]:
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Booking.model_validate(item) for item in data]
        except Exception as e:
            print(f"[BookingRepo] Error loading: {e}")
            return []

    def _save_all(self, bookings: list[Booking]) -> None:
        file_lock = FileLock(self.lock_path, timeout=5)
        with file_lock:
            tmp_path = str(self.filepath) + ".tmp"
            data = [b.model_dump() for b in bookings]
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.filepath))

    def list_all(self) -> list[Booking]:
        return self._load_all()

    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        for b in self._load_all():
            if b.booking_id == booking_id:
                return b
        return None

    def create(self, booking: Booking) -> Booking:
        records = self._load_all()
        if any(b.booking_id == booking.booking_id for b in records):
            raise ValueError(f"Booking with ID {booking.booking_id} already exists.")
        records.append(booking)
        self._save_all(records)
        return booking

    def update(self, booking_id: str, booking: Booking) -> Optional[Booking]:
        records = self._load_all()
        for i, b in enumerate(records):
            if b.booking_id == booking_id:
                records[i] = booking
                self._save_all(records)
                return booking
        return None

    def delete(self, booking_id: str) -> bool:
        records = self._load_all()
        initial_len = len(records)
        records = [b for b in records if b.booking_id != booking_id]
        if len(records) < initial_len:
            self._save_all(records)
            return True
        return False


class PostgresBookingRepository(BookingRepository):
    """
    PostgreSQL implementation of the BookingRepository using SQLAlchemy.
    """
    
    def _to_model(self, db_booking) -> Booking:
        return Booking(
            booking_id=db_booking.booking_id,
            consultant_id=db_booking.consultant_id,
            attendee_name=db_booking.attendee_name,
            attendee_email=db_booking.attendee_email,
            company=db_booking.company,
            topic_summary=db_booking.topic_summary,
            start_iso=db_booking.start_iso,
            end_iso=db_booking.end_iso,
            event_id=db_booking.event_id,
            html_link=db_booking.html_link,
            attendee_link=db_booking.attendee_link,
            meet_link=db_booking.meet_link,
            status=db_booking.status,
            created_at=db_booking.created_at
        )

    def list_all(self) -> list[Booking]:
        from database import SessionLocal, DBBooking
        db = SessionLocal()
        try:
            records = db.query(DBBooking).all()
            return [self._to_model(r) for r in records]
        except Exception as e:
            print(f"[PostgresBookingRepo] Error loading: {e}")
            return []
        finally:
            db.close()

    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        from database import SessionLocal, DBBooking
        db = SessionLocal()
        try:
            record = db.query(DBBooking).filter(DBBooking.booking_id == booking_id).first()
            if record:
                return self._to_model(record)
            return None
        finally:
            db.close()

    def create(self, booking: Booking) -> Booking:
        from database import SessionLocal, DBBooking
        db = SessionLocal()
        try:
            existing = db.query(DBBooking).filter(DBBooking.booking_id == booking.booking_id).first()
            if existing:
                raise ValueError(f"Booking with ID {booking.booking_id} already exists.")
            
            db_booking = DBBooking(
                booking_id=booking.booking_id,
                consultant_id=booking.consultant_id,
                attendee_name=booking.attendee_name,
                attendee_email=booking.attendee_email,
                company=booking.company,
                topic_summary=booking.topic_summary,
                start_iso=booking.start_iso,
                end_iso=booking.end_iso,
                event_id=booking.event_id,
                html_link=booking.html_link,
                attendee_link=booking.attendee_link,
                meet_link=booking.meet_link,
                status=booking.status,
                created_at=booking.created_at
            )
            db.add(db_booking)
            db.commit()
            return booking
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def update(self, booking_id: str, booking: Booking) -> Optional[Booking]:
        from database import SessionLocal, DBBooking
        db = SessionLocal()
        try:
            record = db.query(DBBooking).filter(DBBooking.booking_id == booking_id).first()
            if not record:
                return None
            
            record.consultant_id = booking.consultant_id
            record.attendee_name = booking.attendee_name
            record.attendee_email = booking.attendee_email
            record.company = booking.company
            record.topic_summary = booking.topic_summary
            record.start_iso = booking.start_iso
            record.end_iso = booking.end_iso
            record.event_id = booking.event_id
            record.html_link = booking.html_link
            record.attendee_link = booking.attendee_link
            record.meet_link = booking.meet_link
            record.status = booking.status
            record.created_at = booking.created_at
            
            db.commit()
            return booking
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def delete(self, booking_id: str) -> bool:
        from database import SessionLocal, DBBooking
        db = SessionLocal()
        try:
            record = db.query(DBBooking).filter(DBBooking.booking_id == booking_id).first()
            if not record:
                return False
            db.delete(record)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()


# Canonical repository instance to be used across the app
booking_repo: BookingRepository = PostgresBookingRepository()
