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


class PostgresConsultantRepository(ConsultantRepository):
    """
    PostgreSQL implementation of the ConsultantRepository using SQLAlchemy.
    """
    
    def __init__(self):
        # We rely on the migration script in database.py to handle seeding.
        # But just in case, we could call a similar ensure_seeded here.
        self._ensure_seeded()

    def _ensure_seeded(self):
        from database import SessionLocal, DBConsultant
        from models import ConsultantWorkingHours
        from config import GOOGLE_CALENDAR_ID
        
        db = SessionLocal()
        try:
            count = db.query(DBConsultant).count()
            if count == 0 or (count == 1 and db.query(DBConsultant).first().id == "default_consultant"):
                # Seed default consultants
                default_hours = ConsultantWorkingHours(
                    start="10:00",
                    end="19:00",
                    days=[0, 1, 2, 3, 4]
                )
                default_cal_id = GOOGLE_CALENDAR_ID or "primary"
                
                db.query(DBConsultant).filter(DBConsultant.id == "default_consultant").delete()
                
                c1 = DBConsultant(
                    id="primary_consultant",
                    name="Primary Consultant",
                    email="consultant@agicent.com",
                    active=True,
                    calendar_id=default_cal_id,
                    working_hours=default_hours.model_dump(),
                    leaves=[],
                    unavailabilities=[]
                )
                c2 = DBConsultant(
                    id="business_consultant",
                    name="Business Consultant",
                    email="business@agicent.com",
                    active=True,
                    calendar_id=default_cal_id,
                    working_hours=default_hours.model_dump(),
                    leaves=[],
                    unavailabilities=[]
                )
                c3 = DBConsultant(
                    id="technical_consultant",
                    name="Technical Consultant",
                    email="tech@agicent.com",
                    active=True,
                    calendar_id=default_cal_id,
                    working_hours=default_hours.model_dump(),
                    leaves=[],
                    unavailabilities=[]
                )
                db.add_all([c1, c2, c3])
                db.commit()
        except Exception as e:
            print(f"[PostgresConsultantRepo] Error seeding: {e}")
            db.rollback()
        finally:
            db.close()

    def _to_model(self, db_consultant) -> Consultant:
        from models import ConsultantWorkingHours, ConsultantLeave, ConsultantUnavailability
        return Consultant(
            id=db_consultant.id,
            name=db_consultant.name,
            email=db_consultant.email,
            active=db_consultant.active,
            calendar_id=db_consultant.calendar_id,
            working_hours=ConsultantWorkingHours.model_validate(db_consultant.working_hours),
            leaves=[ConsultantLeave.model_validate(l) for l in (db_consultant.leaves or [])],
            unavailabilities=[ConsultantUnavailability.model_validate(u) for u in (db_consultant.unavailabilities or [])]
        )

    def list_all(self) -> list[Consultant]:
        from database import SessionLocal, DBConsultant
        db = SessionLocal()
        try:
            records = db.query(DBConsultant).all()
            valid_consultants = []
            for record in records:
                try:
                    c = self._to_model(record)
                    cal_id = c.calendar_id
                    
                    if not cal_id or not cal_id.strip():
                        print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to missing calendar_id.")
                        continue
                        
                    cal_id_clean = cal_id.strip().lower()
                    if cal_id_clean in ("c1", "c2", "c3", "test", "test_c", "placeholder"):
                        print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to placeholder/test calendar_id '{cal_id}'.")
                        continue
                        
                    if cal_id_clean != "primary" and "@" not in cal_id_clean:
                        print(f"[ConsultantRepo] WARNING: Rejecting consultant '{c.name}' ({c.id}) due to invalid calendar_id format '{cal_id}'.")
                        continue
                        
                    valid_consultants.append(c)
                except Exception as e:
                    print(f"[ConsultantRepo] WARNING: Failed to validate consultant record {record.id}: {e}")
                    continue
            return valid_consultants
        except Exception as e:
            print(f"[PostgresConsultantRepo] Error loading: {e}")
            return []
        finally:
            db.close()

    def get_by_id(self, consultant_id: str) -> Optional[Consultant]:
        from database import SessionLocal, DBConsultant
        db = SessionLocal()
        try:
            record = db.query(DBConsultant).filter(DBConsultant.id == consultant_id).first()
            if record:
                return self._to_model(record)
            return None
        finally:
            db.close()

    def create(self, consultant: Consultant) -> Consultant:
        from database import SessionLocal, DBConsultant
        db = SessionLocal()
        try:
            existing = db.query(DBConsultant).filter(DBConsultant.id == consultant.id).first()
            if existing:
                raise ValueError(f"Consultant with ID {consultant.id} already exists.")
            
            db_consultant = DBConsultant(
                id=consultant.id,
                name=consultant.name,
                email=consultant.email,
                active=consultant.active,
                calendar_id=consultant.calendar_id,
                working_hours=consultant.working_hours.model_dump(),
                leaves=[l.model_dump() for l in consultant.leaves],
                unavailabilities=[u.model_dump() for u in consultant.unavailabilities]
            )
            db.add(db_consultant)
            db.commit()
            return consultant
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def update(self, consultant_id: str, consultant: Consultant) -> Optional[Consultant]:
        from database import SessionLocal, DBConsultant
        db = SessionLocal()
        try:
            record = db.query(DBConsultant).filter(DBConsultant.id == consultant_id).first()
            if not record:
                return None
            
            record.name = consultant.name
            record.email = consultant.email
            record.active = consultant.active
            record.calendar_id = consultant.calendar_id
            record.working_hours = consultant.working_hours.model_dump()
            record.leaves = [l.model_dump() for l in consultant.leaves]
            record.unavailabilities = [u.model_dump() for u in consultant.unavailabilities]
            
            db.commit()
            return consultant
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def delete(self, consultant_id: str) -> bool:
        from database import SessionLocal, DBConsultant
        db = SessionLocal()
        try:
            record = db.query(DBConsultant).filter(DBConsultant.id == consultant_id).first()
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
consultant_repo: ConsultantRepository = PostgresConsultantRepository()
