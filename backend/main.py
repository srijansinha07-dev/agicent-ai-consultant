"""
main.py — FastAPI application entry point.
"""

import os
import uvicorn
from fastapi import FastAPI

from config import CORS_ORIGINS
from routers import chat, documents, consultations
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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(consultations.router)

# ── Startup ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():

    print("🚀 SERVER STARTED")

    try:
        docstore.load_from_disk()
        print("✅ DOCSTORE LOADED")

    except Exception as e:
        print(f"❌ DOCSTORE ERROR: {e}")

    # ── Ensure website knowledge base exists ───────────



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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                8000
            )
        ),
    )