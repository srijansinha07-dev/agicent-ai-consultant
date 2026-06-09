"""
services/token_analytics.py
────────────────────────────
Lightweight token usage logger for the consultant agent.

Logs a structured line per request to stdout (captured by Railway / Render).
No external dependencies — estimation only (len(text) // 4 ≈ GPT-style tokens).

Usage:
    from services.token_analytics import log_request, estimate_tokens
    log_request(session_id="abc", action="RETRIEVE_AND_ANSWER", prompt=prompt,
                answer=answer, retrieval_used=True, chunk_count=5)
"""
from __future__ import annotations

import json
import time


def estimate_tokens(text: str) -> int:
    """Rough token count: 1 token ≈ 4 chars (GPT tokenizer heuristic)."""
    return max(1, len(text) // 4)


def log_request(
    *,
    session_id: str,
    action: str,
    prompt: str = "",
    answer: str = "",
    retrieval_used: bool = False,
    chunk_count: int = 0,
    context_chars: int = 0,
    extra: dict | None = None,
) -> dict:
    """
    Emit a structured token analytics log line and return the metrics dict.
    """
    input_tokens  = estimate_tokens(prompt)
    output_tokens = estimate_tokens(answer)
    total_tokens  = input_tokens + output_tokens

    metrics = {
        "ts":             int(time.time()),
        "session":        session_id[:16] if session_id else "unknown",
        "action":         action,
        "input_tok_est":  input_tokens,
        "output_tok_est": output_tokens,
        "total_tok_est":  total_tokens,
        "retrieval":      retrieval_used,
        "chunks":         chunk_count,
        "ctx_chars":      context_chars,
    }
    if extra:
        metrics.update(extra)

    print(f"[TOKEN_ANALYTICS] {json.dumps(metrics)}")
    return metrics
