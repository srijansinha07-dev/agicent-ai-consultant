"""
routers/voice.py
────────────────
POST /api/voice/transcribe — multipart audio upload → Faster-Whisper transcript.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import VOICE_ENABLED, VOICE_MAX_AUDIO_BYTES
from models import VoiceTranscriptionResponse
from services.voice_transcription import is_voice_enabled, transcribe_audio

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_endpoint(
    audio: UploadFile = File(..., description="Recorded audio from the browser"),
) -> VoiceTranscriptionResponse:
    if not is_voice_enabled():
        raise HTTPException(
            status_code=503,
            detail="Voice transcription is disabled on this server.",
        )

    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file name is required.")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    if len(content) > VOICE_MAX_AUDIO_BYTES:
        max_mb = VOICE_MAX_AUDIO_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the {max_mb:.0f} MB limit.",
        )

    try:
        result = transcribe_audio(
            audio_bytes=content,
            filename=audio.filename,
            content_type=audio.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        _logger.exception("Voice transcription failed")
        raise HTTPException(
            status_code=500,
            detail="Transcription failed. Please try again.",
        ) from exc

    return VoiceTranscriptionResponse(
        text=result.text,
        language=result.language,
        confidence=result.confidence,
    )
