"""Content-hash cache for hook results.

Avoids re-running hooks on unchanged input by caching results keyed on
SHA-256 content hash.  Supports two TTL tiers:

* **volatile** (300 s / 5 min) — for high-churn checks (SMI freshness)
* **stable**   (3600 s / 1 h)  — for stable inputs (session start, archives)

Usage::

    from hero.core.hooks.cache import hook_cache

    result = hook_cache.get(content_hash)
    if result is not None:
        return result  # skip, cached

    result = run_hook(...)
    hook_cache.set(content_hash, result, ttl=300)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".hero" / "hooks" / "cache"
DEFAULT_VOLATILE_TTL = 300  # 5 minutes
DEFAULT_STABLE_TTL = 3600  # 1 hour


def content_hash(*inputs: str) -> str:
    """Compute a deterministic SHA-256 hash from one or more input strings.

    Args:
        *inputs: One or more strings to hash.

    Returns:
        64-character hex digest.
    """
    joined = "\x00".join(inputs)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    """A single cached hook result."""

    hook_id: str
    content_hash: str
    result: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    ttl: int = DEFAULT_VOLATILE_TTL

    @property
    def expired(self) -> bool:
        """Check whether this entry's TTL has elapsed."""
        return time.time() - self.created_at > self.ttl

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "content_hash": self.content_hash,
            "result": self.result,
            "created_at": self.created_at,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CacheEntry:
        return cls(
            hook_id=d["hook_id"],
            content_hash=d["content_hash"],
            result=d["result"],
            created_at=d["created_at"],
            ttl=d.get("ttl", DEFAULT_VOLATILE_TTL),
        )


class HookCache:
    """Disk-backed content-hash cache with TTL expiry.

    Each hook gets its own JSON file under ``~/.hero/hooks/cache/``.
    Entries are keyed by ``content_hash`` and expire after *ttl* seconds.
    """

    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._stats: dict[str, int] = {"hits": 0, "misses": 0, "expired": 0, "sets": 0}

    def _cache_path(self, hook_id: str) -> Path:
        safe_id = hook_id.replace("/", "_").replace(" ", "_")
        return CACHE_DIR / f"{safe_id}.json"

    def _load(self, hook_id: str) -> dict[str, CacheEntry]:
        path = self._cache_path(hook_id)
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text())
            return {k: CacheEntry.from_dict(v) for k, v in raw.items()}
        except (json.JSONDecodeError, KeyError, TypeError):
            return {}

    def _save(self, hook_id: str, entries: dict[str, CacheEntry]) -> None:
        path = self._cache_path(hook_id)
        raw = {k: v.to_dict() for k, v in entries.items()}
        path.write_text(json.dumps(raw, indent=2))

    def get(self, hook_id: str, content_hash: str) -> dict[str, Any] | None:
        """Retrieve a cached result if it exists and hasn't expired.

        Args:
            hook_id: Hook identifier (e.g. ``read_memory``).
            content_hash: SHA-256 hash of the hook inputs.

        Returns:
            Cached result dict, or ``None`` if not found or expired.
        """
        entries = self._load(hook_id)
        entry = entries.get(content_hash)
        if entry is None:
            self._stats["misses"] += 1
            return None
        if entry.expired:
            self._stats["expired"] += 1
            # Remove expired entry
            del entries[content_hash]
            self._save(hook_id, entries)
            return None
        self._stats["hits"] += 1
        return entry.result

    def set(
        self,
        hook_id: str,
        content_hash: str,
        result: dict[str, Any],
        ttl: int = DEFAULT_VOLATILE_TTL,
    ) -> None:
        """Store a result in the cache.

        Args:
            hook_id: Hook identifier.
            content_hash: SHA-256 hash of the hook inputs.
            result: The result dict to cache.
            ttl: Time-to-live in seconds.
        """
        entries = self._load(hook_id)
        entries[content_hash] = CacheEntry(
            hook_id=hook_id,
            content_hash=content_hash,
            result=result,
            ttl=ttl,
        )
        self._save(hook_id, entries)
        self._stats["sets"] += 1

    def clear(self, hook_id: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            hook_id: If provided, clear only this hook's cache.
                     If ``None``, clear all hook caches.

        Returns:
            Number of cache files removed.
        """
        removed = 0
        if hook_id is not None:
            path = self._cache_path(hook_id)
            if path.exists():
                path.unlink()
                removed = 1
        else:
            for path in CACHE_DIR.glob("*.json"):
                path.unlink()
                removed += 1
        return removed

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss/expired/set counters."""
        return dict(self._stats)


# Singleton instance
hook_cache = HookCache()
