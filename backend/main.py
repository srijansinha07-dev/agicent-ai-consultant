"""
main.py — FastAPI application entry point.
"""

import os
import uvicorn
from fastapi import FastAPI

from config import CORS_ORIGINS
from routers import chat, documents, consultations, calendar, admin, voice
from services import docstore

app = FastAPI(
    title="PDF Assistant API",
    description="OCR-aware PDF assistant",
    version="1.0.0",
)

from fastapi.middleware.cors import (
    CORSMiddleware
)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://pdf-assistant-langgraph.vercel.app",
    "https://agicent-ai-consultant-5x64ee7vu-srijansinha07-devs-projects.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(consultations.router)
app.include_router(calendar.router)
app.include_router(admin.router)
app.include_router(voice.router)


# ── Startup ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():

    print("🚀 SERVER STARTED")

    try:
        docstore.load_from_disk()
        print("✅ DOCSTORE LOADED")

    except Exception as e:
        print(f"❌ DOCSTORE ERROR: {e}")
        
    try:
        from database import init_db
        init_db()
        print("✅ POSTGRES DATABASE INITIALIZED")
    except Exception as e:
        print(f"❌ POSTGRES DATABASE ERROR: {e}")

    # D3: Pre-warm Whisper model in a background daemon thread so the first
    # voice request doesn't cold-start and timeout. A plain daemon thread is
    # used instead of ThreadPoolExecutor because:
    #   - No executor lifecycle or atexit handler to manage
    #   - Daemon flag ensures OS reclaims it on interpreter exit without blocking
    #   - _get_model() uses a global singleton, so duplicate prewarm calls are safe
    try:
        from config import VOICE_ENABLED
        if VOICE_ENABLED:
            import threading

            def _prewarm_whisper():
                try:
                    from services.voice_transcription import _get_model
                    _get_model()
                    print("\u2705 WHISPER MODEL PRELOADED")
                except Exception as exc:
                    print(f"\u26a0\ufe0f  WHISPER PREWARM FAILED (voice will lazy-load on first request): {exc}")

            t = threading.Thread(target=_prewarm_whisper, daemon=True, name="whisper-prewarm")
            t.start()
    except Exception as e:
        print(f"\u26a0\ufe0f  WHISPER PREWARM SKIPPED: {e}")

    # ── Ensure website knowledge base exists ───────────
    try:
        import chromadb
        from chromadb.config import Settings
        from config import CHROMA_PATH
        
        print(f"🔍 [STARTUP CHECK] Opening ChromaDB at exact path: {CHROMA_PATH}")
        
        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        
        collections = client.list_collections()
        print(f"📊 [STARTUP CHECK] Found {len(collections)} collections")
        
        for c in collections:
            count = c.count()
            print(f"   - Collection: '{c.name}' | count: {count}")
            
    except Exception as e:
        print(f"❌ [STARTUP CHECK] ChromaDB Error: {e}")
# ── Routes ──────────────────────────────────────────────

# ── Routes ──────────────────────────────────────────────
@app.get("/")
def root():
    return "OK"


@app.get("/api/health")
def health():
    return "OK"

# ── Run ─────────────────────────────────────────────────

if __name__ == "__main__":
    _port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Binding to port {_port}  (PORT env={os.environ.get('PORT', 'not set')})")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=_port,
    )