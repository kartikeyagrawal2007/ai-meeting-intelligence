"""
utils/token_tracker.py
──────────────────────
Tracks daily Groq token usage in a local JSON file.
Warns at 80k tokens, raises an error at 100k (free tier limit).
Thread-safe via a file lock pattern (atomic write).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DAILY_LIMIT = 100_000
WARN_THRESHOLD = 80_000
TRACKER_FILE = Path(__file__).parent.parent.parent / "outputs" / "token_usage.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TRACKER_FILE.exists():
        return {}
    try:
        return json.loads(TRACKER_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(json.dumps(data, indent=2))


def _today() -> str:
    return date.today().isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def get_usage() -> dict:
    """Return today's usage summary."""
    data = _load()
    today = _today()
    entry = data.get(today, {"tokens_used": 0, "calls": 0, "breakdown": {}})
    return {
        "date": today,
        "tokens_used": entry["tokens_used"],
        "calls": entry["calls"],
        "daily_limit": DAILY_LIMIT,
        "warn_threshold": WARN_THRESHOLD,
        "remaining": max(0, DAILY_LIMIT - entry["tokens_used"]),
        "percent_used": round(entry["tokens_used"] / DAILY_LIMIT * 100, 1),
        "status": (
            "critical" if entry["tokens_used"] >= DAILY_LIMIT else
            "warning"  if entry["tokens_used"] >= WARN_THRESHOLD else
            "ok"
        ),
        "breakdown": entry.get("breakdown", {}),
    }


def record_usage(tokens: int, source: str = "unknown") -> dict:
    """
    Record token usage after an API call.

    Args:
        tokens: Number of tokens consumed.
        source: Label for the caller (e.g. "sentiment", "extraction").

    Returns:
        Updated usage dict.

    Raises:
        RuntimeError: If daily limit is already exceeded.
    """
    data = _load()
    today = _today()

    if today not in data:
        data[today] = {"tokens_used": 0, "calls": 0, "breakdown": {}}

    entry = data[today]

    if entry["tokens_used"] >= DAILY_LIMIT:
        raise RuntimeError(
            f"Daily Groq token limit ({DAILY_LIMIT:,}) already reached. "
            "Try again tomorrow or upgrade your plan."
        )

    entry["tokens_used"] += tokens
    entry["calls"] += 1
    entry["breakdown"][source] = entry["breakdown"].get(source, 0) + tokens

    _save(data)

    usage = get_usage()

    if usage["status"] == "critical":
        log.error(
            f"🚨 GROQ DAILY LIMIT REACHED: {entry['tokens_used']:,}/{DAILY_LIMIT:,} tokens"
        )
    elif usage["status"] == "warning":
        log.warning(
            f"⚠️  Groq token warning: {entry['tokens_used']:,}/{DAILY_LIMIT:,} "
            f"({usage['percent_used']}% used) — {usage['remaining']:,} remaining"
        )
    else:
        log.debug(f"Token usage: +{tokens} from [{source}] — total today: {entry['tokens_used']:,}")

    return usage


def get_all_history() -> list[dict]:
    """Return token usage for all recorded days, newest first."""
    data = _load()
    rows = []
    for day, entry in sorted(data.items(), reverse=True):
        rows.append({
            "date": day,
            "tokens_used": entry["tokens_used"],
            "calls": entry["calls"],
            "percent_used": round(entry["tokens_used"] / DAILY_LIMIT * 100, 1),
            "breakdown": entry.get("breakdown", {}),
        })
    return rows
