"""
services/voice_transcription.py
───────────────────────────────
Faster-Whisper speech-to-text with lazy singleton model loading (CPU).
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import (
    VOICE_ENABLED,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)

_logger = logging.getLogger(__name__)

_model: object | None = None
_model_lock = __import__('threading').Lock()

_SUPPORTED_EXTENSIONS = frozenset({
    ".webm", ".wav", ".ogg", ".mp4", ".m4a", ".mp3", ".flac", ".opus",
})

WHISPER_TECHNICAL_PROMPT = (
    "AI, ML, NLP, API, MVP, Frontend, Backend, Database, Dashboard, Chatbot, "
    "Recruitment, Candidate, Resume, Interview, Scheduling, Healthcare, "
    "FastAPI, React, Node.js, PostgreSQL, AWS, Docker, Kubernetes, LangChain, "
    "OpenAI, Gemini, Claude, ChromaDB, Railway, Vercel"
)

CORRECTION_DICT = {
    # Recruitment / HR
    "rikrootament": "recruitment",
    "reekrootment": "recruitment",
    "rikrootment": "recruitment",
    "rikrooting": "recruiting",
    "reejiyoom": "resume",
    "reejiyooms": "resumes",
    "rijyum": "resume",
    "kanidets": "candidates",
    "kanidet": "candidate",
    "kanidait": "candidate",
    "intarviyoo": "interview",
    "intarvyoo": "interview",
    "intarview": "interview",
    "shedooling": "scheduling",
    "skedooling": "scheduling",
    "rainking": "ranking",
    "selektion": "selection",
    # Platform / Product
    "pletphorm": "platform",
    "plaetphorm": "platform",
    "daishbord": "dashboard",
    "dasbord": "dashboard",
    "chaetbot": "chatbot",
    "chaatbot": "chatbot",
    "deploiment": "deployment",
    "deploiement": "deployment",
    "feechur": "feature",
    "feechars": "features",
    "skreen": "screening",
    "payement": "payment",
    # Infrastructure / Tech
    "detabes": "database",
    "detabais": "database",
    "ditabes": "database",
    "pavard": "powered",
    "asistent": "assistant",
    "asistant": "assistant",
    # Support
    "sapot": "support",
    "saport": "support",
    # Healthcare - all phonetic variants
    "helthcare": "healthcare",
    "helth keyar": "healthcare",
    "health keyar": "healthcare",
    "helth-keyar": "healthcare",
    "hil thakya": "healthcare",
    "hil thaakya": "healthcare",
    "hil takia": "healthcare",
    "hel thakya": "healthcare",
    "hel thaakya": "healthcare",
    "hel takia": "healthcare",
    "helth ker": "healthcare",
    "helth care": "healthcare",
}

PROTECTED_VOCABULARY = {
    "api", "fastapi", "react", "postgresql", "aws", "docker",
    "kubernetes", "langchain", "openai", "gemini", "claude",
    "chromadb", "railway", "vercel", "node.js", "mvp",
    "frontend", "backend", "database", "dashboard", "chatbot",
    "recruitment", "candidate", "resume", "interview", "scheduling",
    "healthcare",
}


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    confidence: Optional[float] = None


def is_voice_enabled() -> bool:
    return VOICE_ENABLED


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    content_type: str | None = None,
) -> TranscriptionResult:
    if not VOICE_ENABLED:
        raise RuntimeError("Voice transcription is disabled.")

    if not audio_bytes:
        raise ValueError("Audio payload is empty.")

    suffix = _resolve_suffix(filename, content_type)
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format '{suffix}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )

    temp_path = _write_temp_audio(audio_bytes, suffix)
    try:
        import time
        model = _get_model()
        segments, info = model.transcribe(
            temp_path,
            beam_size=3,
            language=None,
            task="transcribe",
            initial_prompt=WHISPER_TECHNICAL_PROMPT,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
            temperature=0.0,
        )

        parts: list[str] = []
        start_time = time.time()
        timeout_seconds = 90.0

        for segment in segments:
            if time.time() - start_time > timeout_seconds:
                _logger.warning("Transcription loop timed out after %.1f seconds", timeout_seconds)
                raise RuntimeError("Transcription timed out. The audio may be too noisy.")
            
            text = (segment.text or "").strip()
            if text:
                parts.append(text)

        transcript = " ".join(parts).strip()
        if not transcript:
            raise ValueError("No speech detected in the audio.")

        language = _normalize_language(info.language or "en")
        confidence: Optional[float] = None
        if info.language_probability is not None:
            confidence = float(info.language_probability)

        if any("\u0900" <= c <= "\u097f" for c in transcript):
            try:
                original_transcript = transcript
                transcript = normalize_hinglish(transcript)
                transcript = correct_technical_vocabulary(transcript)
                language = "hi"  # Ensure frontend gets Hinglish flag
            except Exception as e:
                _logger.error("Failed to normalize Hinglish, falling back to original transcript: %s", e)
                transcript = original_transcript

        return TranscriptionResult(
            text=transcript,
            language=language,
            confidence=confidence,
        )
    finally:
        _safe_remove(temp_path)


def _get_model() -> object:
    global _model
    # Fast path — no lock needed once model is loaded
    if _model is not None:
        return _model
    # Slow path — acquire lock to prevent concurrent loads
    # (e.g. prewarm daemon thread racing with first real request)
    with _model_lock:
        if _model is not None:  # double-checked locking
            return _model

        from faster_whisper import WhisperModel
        from config import log_memory

        log_memory("Before Whisper model initialization")
        _logger.info(
            "Loading Whisper model size=%s device=%s compute_type=%s",
            WHISPER_MODEL_SIZE,
            WHISPER_DEVICE,
            WHISPER_COMPUTE_TYPE,
        )

        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        log_memory("After Whisper model initialization")
        _logger.info("Whisper model loaded.")
        return _model


def _write_temp_audio(audio_bytes: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="voice_")
    os.close(fd)
    Path(path).write_bytes(audio_bytes)
    return path


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError as exc:
        _logger.warning("Failed to remove temp audio file %s: %s", path, exc)


def _resolve_suffix(filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in _SUPPORTED_EXTENSIONS:
        return suffix

    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        mime_map = {
            "audio/webm": ".webm",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/mp4": ".mp4",
            "audio/m4a": ".m4a",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/flac": ".flac",
            "audio/opus": ".opus",
        }
        mapped = mime_map.get(mime)
        if mapped:
            return mapped

    return suffix or ".webm"


def _normalize_language(language: str) -> str:
    code = language.lower().strip()
    if code.startswith("hi"):
        return "hi"
    if code.startswith("en"):
        return "en"
    return code.split("-")[0] if "-" in code else code


def _process_hindi_block(text: str) -> str:
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except ImportError as e:
        _logger.error("indic_transliteration is not installed. Skipping normalization. Error: %s", e)
        return text

    # 1. Transliterate to ITRANS
    t = transliterate(text, sanscript.DEVANAGARI, "itrans")
    
    # 2. Anusvara and Nasals
    t = t.replace('M', 'n').replace('.N', 'n').replace('.n', 'n')
    
    # 3. Trailing Schwa deletion (only lowercase 'a' at word ends)
    t = re.sub(r'a\b', '', t)
    
    # 4. Medial Schwa deletion & Specific Conversational Fixes
    t = re.sub(r'\bchAhatA\b', 'chAhtA', t)
    
    # 5. Vowels & Consonants mapped to conversational Hinglish
    t = re.sub(r'\bA', 'aa', t)
    t = t.replace('A', 'a')
    t = t.replace('uu', 'oo').replace('U', 'oo')
    t = t.replace('ii', 'ee').replace('I', 'ee')
    t = t.replace('chCh', 'chh').replace('Ch', 'chh')
    t = re.sub(r'\bkyaa\b', 'kya', t, flags=re.IGNORECASE)
    
    # 6. Final cleanups
    t = t.lower()
    t = re.sub(r'\byah\b', 'yeh', t)
    t = re.sub(r'\bvah\b', 'woh', t)
    t = t.replace('|', '.')
    
    return t


def normalize_hinglish(text: str) -> str:
    def replacer(match):
        return _process_hindi_block(match.group(0))
        
    return re.sub(r'[\u0900-\u097F]+', replacer, text)


def correct_technical_vocabulary(text: str) -> str:
    """
    Post-normalization correction layer for technical English words that were
    phonetically spelled in Devanagari by Whisper.

    Order of operations:
      1. Multi-word phrase replacements (e.g. "hil thakya" -> "healthcare")
      2. Per-word direct dictionary lookup
      3. Per-word conservative fuzzy match against PROTECTED_VOCABULARY
    """
    import difflib

    # 1. Multi-word phrase corrections first (before tokenization splits them)
    result = text
    for phrase, replacement in CORRECTION_DICT.items():
        if " " in phrase or "-" in phrase:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            result = pattern.sub(replacement, result)

    # 2. Per-word corrections
    stop_words = {
        "aur", "kya", "hain", "hai", "tha", "thi", "ka", "ki", "ke",
        "mein", "se", "ko", "par", "hi", "bhi", "ek", "vs", "ya",
    }

    canonical_map = {
        "api": "API", "fastapi": "FastAPI", "react": "React",
        "postgresql": "PostgreSQL", "aws": "AWS", "docker": "Docker",
        "kubernetes": "Kubernetes", "langchain": "LangChain",
        "openai": "OpenAI", "gemini": "Gemini", "claude": "Claude",
        "chromadb": "ChromaDB", "railway": "Railway", "vercel": "Vercel",
        "node.js": "Node.js", "mvp": "MVP", "frontend": "Frontend",
        "backend": "Backend", "database": "Database", "dashboard": "Dashboard",
        "chatbot": "Chatbot", "recruitment": "Recruitment",
        "candidate": "Candidate", "resume": "Resume",
        "interview": "Interview", "scheduling": "Scheduling",
        "healthcare": "Healthcare",
    }

    words = result.split()
    corrected_words = []

    for word in words:
        # Strip trailing punctuation for matching, remember suffix
        suffix_match = re.search(r'[^\w]$', word)
        suffix = suffix_match.group(0) if suffix_match else ""
        core = word[: -len(suffix)] if suffix else word
        clean = core.lower()

        # 2a. Direct single-word dictionary lookup
        if clean in CORRECTION_DICT:
            replacement = CORRECTION_DICT[clean]
            # Preserve title / upper case of original
            if core[0].isupper():
                replacement = replacement.title()
            corrected_words.append(replacement + suffix)
            continue

        # 2b. Conservative fuzzy match against protected vocabulary (cutoff=0.85)
        if len(clean) >= 4 and clean not in stop_words and not clean.isdigit():
            matches = difflib.get_close_matches(
                clean, PROTECTED_VOCABULARY, n=1, cutoff=0.85
            )
            if matches:
                word = canonical_map.get(matches[0], matches[0]) + suffix

        corrected_words.append(word)

    return " ".join(corrected_words)

