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
        import threading
        def _init_db_bg():
            try:
                from database import init_db
                init_db()
                print("\u2705 POSTGRES DATABASE INITIALIZED")
            except Exception as exc:
                print(f"\u274c POSTGRES DATABASE ERROR: {exc}")
        threading.Thread(target=_init_db_bg, daemon=True, name="db-init").start()
    except Exception as e:
        print(f"\u274c POSTGRES DATABASE ERROR: {e}")

    # D3: Pre-warm Whisper model in a background daemon thread so the first
    # voice request doesn't cold-start and timeout. A plain daemon thread is
    # used instead of ThreadPoolExecutor because:
    #   - No executor lifecycle or atexit handler to manage
    #   - Daemon flag ensures OS reclaims it on interpreter exit without blocking
    #   - _get_model() uses a global singleton, so duplicate prewarm calls are safe
    try:
        from config import VOICE_ENABLED
        import threading

        def _prewarm_models():
            import os
            
            def get_mem_mb():
                try:
                    with open('/proc/self/status') as f:
                        for line in f:
                            if line.startswith('VmRSS:'):
                                return int(line.split()[1]) / 1024
                except:
                    pass
                return 0.0

            mem_start = get_mem_mb()
            print(f"📊 [MEMORY] Startup base memory: {mem_start:.2f} MB")

            try:
                print("⏳ PREWARMING EMBEDDER (BACKGROUND)...")
                from services.vectorstore import _get_embedder
                _get_embedder()
                mem_emb = get_mem_mb()
                print(f"✅ EMBEDDER PREWARMED. Memory: {mem_emb:.2f} MB")
            except Exception as e:
                print(f"❌ EMBEDDER PREWARM FAILED: {e}")

            if VOICE_ENABLED:
                try:
                    print("⏳ PREWARMING WHISPER (BACKGROUND)...")
                    from services.voice_transcription import _get_model
                    _get_model()
                    mem_wh = get_mem_mb()
                    print(f"✅ WHISPER PREWARMED. Memory: {mem_wh:.2f} MB")
                except Exception as exc:
                    print(f"⚠️ WHISPER PREWARM FAILED (voice will lazy-load): {exc}")

        t = threading.Thread(target=_prewarm_models, daemon=True, name="model-prewarm")
        t.start()
    except Exception as e:
        print(f"⚠️ MODEL PREWARM SKIPPED: {e}")

    # ── Ensure website knowledge base exists (non-blocking) ────────────────
    def _check_chroma_bg():
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
                if c.name == "agicent-website" and count < 4000:
                    print(f"⚠️ [STARTUP CHECK] Collection {c.name} has only {count} chunks (expected ~4020). Rebuilding from full dataset...")
                    try:
                        from ingest_website import ingest_website
                        ingest_website()
                        print(f"✅ [STARTUP CHECK] Rebuild complete. New count: {c.count()}")
                    except Exception as rebuild_exc:
                        print(f"❌ [STARTUP CHECK] Failed to rebuild: {rebuild_exc}")

        except Exception as e:
            print(f"❌ [STARTUP CHECK] ChromaDB Error: {e}")

    import threading
    threading.Thread(target=_check_chroma_bg, daemon=True, name="chroma-check").start()
# ── Routes ──────────────────────────────────────────────

# ── Routes ──────────────────────────────────────────────
@app.get("/")
def root():
    return "OK"


@app.get("/health")
def health_railway():
    """Railway health check endpoint — must return 200 immediately."""
    return {"status": "ok"}


@app.get("/api/health")
def health():
    """Legacy health endpoint — kept for backward compatibility."""
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