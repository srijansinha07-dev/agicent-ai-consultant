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


# Canonical repository instance to be used across the app
booking_repo: BookingRepository = JSONBookingRepository()
