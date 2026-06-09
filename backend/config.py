"""
config.py — centralised configuration for the PDF Assistant backend.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
UPLOAD_DIR    = BASE_DIR / "uploads"
CHROMA_DIR    = BASE_DIR / "chroma_db"
CONSULTATIONS_FILE = BASE_DIR / "data" / "consultations.json"

UPLOAD_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)
CONSULTATIONS_FILE.parent.mkdir(exist_ok=True)

# ── Consultation requests (HubSpot/CRM ready) ─────────────────────────────
# If set, we forward the request payload to this webhook URL.
CONSULTATION_FORWARD_URL = os.getenv("CONSULTATION_FORWARD_URL", "").strip()

# If set, admin staff can fetch stored consultations with this key.
CONSULTATION_ADMIN_KEY = os.getenv("CONSULTATION_ADMIN_KEY", "").strip()

# ── Consultant Agent ───────────────────────────────────────────────────────
# Master toggle: "false" falls back to legacy langgraph path for website docs.
CONSULTANT_AGENT_ENABLED = os.getenv("CONSULTANT_AGENT_ENABLED", "true").lower() == "true"

# Conversation state TTL in seconds (default 2 hours).
CONVERSATION_STATE_TTL_SECONDS = int(os.getenv("CONVERSATION_STATE_TTL_SECONDS", "7200"))

# ── Google Calendar Integration ────────────────────────────────────────────
# Base64-encoded service account JSON (preferred for production).
GOOGLE_CALENDAR_CREDENTIALS_JSON = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", "").strip()

# Calendar to create events on ("primary" or full calendar ID).
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()

# File-based OAuth token (used when GOOGLE_CALENDAR_CREDENTIALS_JSON is empty).
GOOGLE_OAUTH_TOKEN_FILE = os.getenv(
    "GOOGLE_OAUTH_TOKEN_FILE",
    str(BASE_DIR / "data" / "calendar_token.json"),
).strip()

# File-based OAuth client secrets (first-time auth flow).
GOOGLE_CLIENT_SECRETS_FILE = os.getenv(
    "GOOGLE_CLIENT_SECRETS_FILE",
    str(BASE_DIR / "data" / "calendar_credentials.json"),
).strip()

# Duration of discovery/consultation calls in minutes.
MEETING_DURATION_MINUTES = int(os.getenv("MEETING_DURATION_MINUTES", "45"))

# IANA timezone for calendar events.
MEETING_TIMEZONE = os.getenv("MEETING_TIMEZONE", "America/New_York").strip()

# ── Ollama models ──────────────────────────────────────────────────────────


USE_GROQ = os.getenv(
    "USE_GROQ",
    "False"
).lower() == "true"

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    ""
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)
print("USE_GROQ:", USE_GROQ)
print("MODEL:", GROQ_MODEL)
print("KEY EXISTS:", bool(GROQ_API_KEY))
# ── ChromaDB ───────────────────────────────────────────────────────────────
CHROMA_PATH = str(CHROMA_DIR)



# ── Retrieval ──────────────────────────────────────────────────────────────
TOP_K_SEMANTIC = 10
TOP_K_BM25     = 10
TOP_K_FINAL = 6           # chunks sent to LLM after reranking

# ── Reranker ───────────────────────────────────────────────────────────────
RERANKER_MODEL = None

# ── CORS ───────────────────────────────────────────────────────────────────
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",

    # Vercel domains
    "https://lumina-pdf-assistant-iepxl5yae-srijansinha07-devs-projects.vercel.app",
    "https://lumina-pdf-assistant.vercel.app",
]
