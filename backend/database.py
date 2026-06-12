import os
import json
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, Text, JSON, func
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agicent")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ORM Models

class DBBooking(Base):
    __tablename__ = "bookings"
    
    booking_id = Column(String, primary_key=True, index=True)
    consultant_id = Column(String, index=True)
    attendee_name = Column(String)
    attendee_email = Column(String)
    company = Column(String, nullable=True)
    topic_summary = Column(Text, nullable=True)
    start_iso = Column(String)
    end_iso = Column(String)
    event_id = Column(String)
    html_link = Column(String)
    attendee_link = Column(String, nullable=True)
    meet_link = Column(String, nullable=True)
    status = Column(String)
    created_at = Column(String)

class DBConsultant(Base):
    __tablename__ = "consultants"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    active = Column(Boolean, default=True)
    calendar_id = Column(String)
    # Store JSON strings or JSONB for these nested structures
    working_hours = Column(JSON)
    leaves = Column(JSON)
    unavailabilities = Column(JSON)

class DBConsultation(Base):
    __tablename__ = "consultations"
    
    consultation_id = Column(String, primary_key=True, index=True)
    created_at = Column(String)
    user_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True)
    name = Column(String)
    email = Column(String)
    company = Column(String)
    project_description = Column(Text)
    budget = Column(String, nullable=True)
    timeline = Column(String, nullable=True)
    project_summary = Column(Text)
    conversation_history = Column(JSON)

class DBSchedulingState(Base):
    __tablename__ = "scheduling_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    last_assigned_id = Column(String, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Run migration from JSON to DB if DB is empty
    from sqlalchemy.orm import Session
    from config import BASE_DIR
    import json
    
    db = SessionLocal()
    try:
        # Migrate Consultants
        if db.query(DBConsultant).count() == 0:
            consultants_file = BASE_DIR / "data" / "consultants.json"
            if consultants_file.exists():
                try:
                    with open(consultants_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            db_consultant = DBConsultant(
                                id=item["id"],
                                name=item["name"],
                                email=item["email"],
                                active=item.get("active", True),
                                calendar_id=item["calendar_id"],
                                working_hours=item.get("working_hours", {}),
                                leaves=item.get("leaves", []),
                                unavailabilities=item.get("unavailabilities", [])
                            )
                            db.add(db_consultant)
                    db.commit()
                    print("Migrated consultants from JSON")
                except Exception as e:
                    print(f"Error migrating consultants: {e}")
                    db.rollback()

        # Migrate Bookings
        if db.query(DBBooking).count() == 0:
            bookings_file = BASE_DIR / "data" / "bookings.json"
            if bookings_file.exists():
                try:
                    with open(bookings_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            db_booking = DBBooking(
                                booking_id=item["booking_id"],
                                consultant_id=item["consultant_id"],
                                attendee_name=item["attendee_name"],
                                attendee_email=item["attendee_email"],
                                company=item.get("company"),
                                topic_summary=item.get("topic_summary"),
                                start_iso=item["start_iso"],
                                end_iso=item["end_iso"],
                                event_id=item["event_id"],
                                html_link=item["html_link"],
                                attendee_link=item.get("attendee_link"),
                                meet_link=item.get("meet_link"),
                                status=item["status"],
                                created_at=item["created_at"]
                            )
                            db.add(db_booking)
                    db.commit()
                    print("Migrated bookings from JSON")
                except Exception as e:
                    print(f"Error migrating bookings: {e}")
                    db.rollback()

        # Migrate Consultations
        if db.query(DBConsultation).count() == 0:
            consultations_file = BASE_DIR / "data" / "consultations.json"
            if consultations_file.exists():
                try:
                    with open(consultations_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            db_consultation = DBConsultation(
                                consultation_id=item["consultation_id"],
                                created_at=item["created_at"],
                                user_id=item.get("user_id"),
                                session_id=item.get("session_id"),
                                name=item["name"],
                                email=item["email"],
                                company=item.get("company", ""),
                                project_description=item.get("project_description", ""),
                                budget=item.get("budget"),
                                timeline=item.get("timeline"),
                                project_summary=item.get("project_summary", ""),
                                conversation_history=item.get("conversation_history", [])
                            )
                            db.add(db_consultation)
                    db.commit()
                    print("Migrated consultations from JSON")
                except Exception as e:
                    print(f"Error migrating consultations: {e}")
                    db.rollback()

        # Migrate Scheduling State
        if db.query(DBSchedulingState).count() == 0:
            state_file = BASE_DIR / "data" / "scheduling_state.json"
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "last_assigned_id" in data:
                            db_state = DBSchedulingState(last_assigned_id=data["last_assigned_id"])
                            db.add(db_state)
                            db.commit()
                            print("Migrated scheduling state from JSON")
                except Exception as e:
                    print(f"Error migrating scheduling state: {e}")
                    db.rollback()
    finally:
        db.close()
