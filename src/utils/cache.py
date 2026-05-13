"""
utils/cache.py
──────────────
File-based response cache using MD5 hashes.

- Transcription results: keyed by audio file MD5
- Extraction/sentiment results: keyed by transcript content MD5

Cache entries are stored as JSON files in outputs/cache/.
Each entry has a timestamp so old caches can be expired.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "outputs" / "cache"
CACHE_TTL_HOURS = 72  # Expire cache entries after 3 days


# ── Hashing ───────────────────────────────────────────────────────────────────

def hash_file(filepath: str) -> str:
    """Compute MD5 hash of a file's contents."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_text(text: str) -> str:
    """Compute MD5 hash of a string."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def hash_dict(data: dict) -> str:
    """Compute MD5 hash of a dict (serialised deterministically)."""
    serialised = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(serialised.encode("utf-8")).hexdigest()


# ── Cache I/O ─────────────────────────────────────────────────────────────────

def _cache_path(key: str, namespace: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{namespace}_{key}.json"


def _is_expired(entry: dict) -> bool:
    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
        return datetime.utcnow() - cached_at > timedelta(hours=CACHE_TTL_HOURS)
    except (KeyError, ValueError):
        return True


def get(key: str, namespace: str = "default") -> dict | None:
    """
    Retrieve a cached value.

    Returns:
        The cached dict if found and not expired, else None.
    """
    path = _cache_path(key, namespace)
    if not path.exists():
        log.debug(f"Cache MISS [{namespace}] key={key[:8]}…")
        return None

    try:
        entry = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        log.warning(f"Cache read error [{namespace}] key={key[:8]}… — deleting")
        path.unlink(missing_ok=True)
        return None

    if _is_expired(entry):
        log.debug(f"Cache EXPIRED [{namespace}] key={key[:8]}… — deleting")
        path.unlink(missing_ok=True)
        return None

    log.info(f"Cache HIT [{namespace}] key={key[:8]}… (cached {entry['cached_at']})")
    return entry.get("data")


def set(key: str, data: dict | list, namespace: str = "default") -> None:
    """Store a value in the cache."""
    path = _cache_path(key, namespace)
    entry = {
        "cached_at": datetime.utcnow().isoformat(),
        "namespace": namespace,
        "key": key,
        "data": data,
    }
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False))
    log.debug(f"Cache SET [{namespace}] key={key[:8]}…")


def invalidate(key: str, namespace: str = "default") -> None:
    """Remove a specific cache entry."""
    path = _cache_path(key, namespace)
    path.unlink(missing_ok=True)
    log.debug(f"Cache INVALIDATED [{namespace}] key={key[:8]}…")


def clear_all() -> int:
    """Delete all cache files. Returns count deleted."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    log.info(f"Cache cleared: {count} entries removed")
    return count


def stats() -> dict:
    """Return cache statistics."""
    if not CACHE_DIR.exists():
        return {"total": 0, "size_kb": 0, "namespaces": {}}

    files = list(CACHE_DIR.glob("*.json"))
    total_bytes = sum(f.stat().st_size for f in files)
    namespaces: dict[str, int] = {}

    for f in files:
        parts = f.stem.split("_", 1)
        ns = parts[0] if len(parts) > 1 else "default"
        namespaces[ns] = namespaces.get(ns, 0) + 1

    return {
        "total": len(files),
        "size_kb": round(total_bytes / 1024, 1),
        "namespaces": namespaces,
    }
