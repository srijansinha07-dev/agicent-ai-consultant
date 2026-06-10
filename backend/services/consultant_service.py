"""
services/consultant_service.py
───────────────────────────────
Repository and service layer for managing consultants.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from filelock import FileLock
from typing import Optional

from models import Consultant, ConsultantWorkingHours
from config import BASE_DIR, GOOGLE_CALENDAR_ID

CONSULTANTS_FILE = BASE_DIR / "data" / "consultants.json"


class ConsultantRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Consultant]:
        """List all consultants."""
        pass

    @abstractmethod
    def get_by_id(self, consultant_id: str) -> Optional[Consultant]:
        """Get a consultant by ID."""
        pass

    @abstractmethod
    def create(self, consultant: Consultant) -> Consultant:
        """Create a new consultant."""
        pass

    @abstractmethod
    def update(self, consultant_id: str, consultant: Consultant) -> Optional[Consultant]:
        """Update an existing consultant."""
        pass

    @abstractmethod
    def delete(self, consultant_id: str) -> bool:
        """Delete a consultant."""
        pass


class JSONConsultantRepository(ConsultantRepository):
    """
    JSON file implementation of the ConsultantRepository.
    Uses file lock for safety and handles self-seeding.
    """

    def __init__(self, filepath: Path = CONSULTANTS_FILE):
        self.filepath = filepath
        self.lock_path = str(filepath) + ".lock"
        self.filepath.parent.mkdir(exist_ok=True)
        self._ensure_seeded()

    def _ensure_seeded(self):
        """Seed default consultants if none exist or only the single default remains."""
        should_seed = False
        if not self.filepath.exists():
            should_seed = True
        else:
            try:
                # If there are no valid consultants, or only the old default remains, seed the three test ones
                valid_existing = self._load_all()
                if not valid_existing or (len(valid_existing) == 1 and valid_existing[0].id == "default_consultant"):
                    should_seed = True
            except Exception:
                should_seed = True

        if should_seed:
            default_hours = ConsultantWorkingHours(
                start="10:00",
                end="19:00",
                days=[0, 1, 2, 3, 4]  # Mon-Fri
            )
            default_cal_id = GOOGLE_CALENDAR_ID or "primary"
            c1 = Consultant(
                id="primary_consultant",
                name="Primary Consultant",
                email="consultant@agicent.com",
                active=True,
                calendar_id=default_cal_id,
                working_hours=default_hours,
                leaves=[],
                unavailabilities=[]
            )
            c2 = Consultant(
                id="business_consultant",
                name="Business Consultant",
                email="business@agicent.com",
                active=True,
                calendar_id=default_cal_id,
                working_hours=default_hours,
                leaves=[],
                unavailabilities=[]
            )
            c3 = Consultant(
                id="technical_consultant",
                name="Technical Consultant",
                email="tech@agicent.com",
                active=True,
                calendar_id=default_cal_id,
                working_hours=default_hours,
                leaves=[],
                unavailabilities=[]
            )
            self._save_all([c1, c2, c3])

    def _load_all(self) -> list[Consultant]:
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                valid_consultants = []
                for item in data:
                    try:
                        c = Consultant.model_validate(item)
                        cal_id = c.calendar_id
                        
                        # 1. Reject empty calendar_id
                        if not cal_id or not cal_id.strip():
                            print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to missing calendar_id.")
                            continue
                            
                        # 2. Reject placeholder/test calendar_ids
                        cal_id_clean = cal_id.strip().lower()
                        if cal_id_clean in ("c1", "c2", "c3", "test", "test_c", "placeholder"):
                            print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to placeholder/test calendar_id '{cal_id}'.")
                            continue
                            
                        # 3. Reject invalid format (must be "primary" or contain "@")
                        if cal_id_clean != "primary" and "@" not in cal_id_clean:
                            print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to invalid calendar_id format '{cal_id}'.")
                            continue
                            
                        valid_consultants.append(c)
                    except Exception as e:
                        print(f"[ConsultantRepo] WARNING: Failed to validate consultant record {item}: {e}")
                        continue
                return valid_consultants
        except Exception as e:
            print(f"[ConsultantRepo] Error loading: {e}")
            return []

    def _save_all(self, consultants: list[Consultant]) -> None:
        file_lock = FileLock(self.lock_path, timeout=5)
        with file_lock:
            tmp_path = str(self.filepath) + ".tmp"
            data = [c.model_dump() for c in consultants]
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.filepath))

    def list_all(self) -> list[Consultant]:
        return self._load_all()

    def get_by_id(self, consultant_id: str) -> Optional[Consultant]:
        for c in self._load_all():
            if c.id == consultant_id:
                return c
        return None

    def create(self, consultant: Consultant) -> Consultant:
        records = self._load_all()
        # Ensure ID uniqueness
        if any(c.id == consultant.id for c in records):
            raise ValueError(f"Consultant with ID {consultant.id} already exists.")
        records.append(consultant)
        self._save_all(records)
        return consultant

    def update(self, consultant_id: str, consultant: Consultant) -> Optional[Consultant]:
        records = self._load_all()
        for i, c in enumerate(records):
            if c.id == consultant_id:
                records[i] = consultant
                self._save_all(records)
                return consultant
        return None

    def delete(self, consultant_id: str) -> bool:
        records = self._load_all()
        initial_len = len(records)
        records = [c for c in records if c.id != consultant_id]
        if len(records) < initial_len:
            self._save_all(records)
            return True
        return False


# Canonical repository instance to be used across the app
consultant_repo: ConsultantRepository = JSONConsultantRepository()
