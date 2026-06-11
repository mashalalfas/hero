"""StateCache — LRU in-memory cache for sandbox state files.

Eliminates redundant disk reads by caching ``SandboxState.load()`` results
with TTL-based invalidation. Default TTL: 30 s.

Cache hits skip disk I/O entirely; cache misses read from disk and store
in cache. Auto-invalidated on spawn/complete (mutations).

Usage::

    from hero.state.cache import StateCache

    cache = StateCache()
    states = cache.batch_load(["qlearner", "fury-os", "sook-pro"])
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hero.state.sandbox import SandboxState  # noqa: F401


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A single cached sandbox state with TTL."""

    data: dict[str, Any]
    """Full state dict returned by ``SandboxState.load()``."""

    ttl: float = 30.0
    """Time-to-live in seconds."""

    created_at: float = field(default_factory=time.time)
    """Unix timestamp of when this entry was created / last refreshed."""

    @property
    def is_valid(self) -> bool:
        """True while ``time.time() - created_at < ttl``."""
        return (time.time() - self.created_at) < self.ttl

    def refresh(self) -> None:
        """Update ``created_at`` to now."""
        self.created_at = time.time()


# Backwards-compat alias so external code that imports ``_CacheEntry`` works.
_CacheEntry = CacheEntry  # type: ignore[misc]


class StateCache:
    """LRU cache for sandbox state files with TTL-based invalidation.

    Thread-safe: all mutations are guarded by an internal ``threading.Lock``.

    Parameters
    ----------
    default_ttl:
        Seconds before an entry is considered stale (default: 30 s).
    maxsize:
        Maximum number of entries before LRU eviction kicks in.
    """

    def __init__(self, default_ttl: float = 30.0, maxsize: int = 128) -> None:
        self.default_ttl = default_ttl
        self.maxsize = maxsize
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _touch(self, key: str) -> None:
        """Mark *key* as most-recently-used."""
        self._store.move_to_end(key)

    def _evict_lru(self) -> None:
        """Evict the LRU entry if at capacity."""
        if len(self._store) >= self.maxsize:
            self._store.popitem(last=False)
            self.evictions += 1

    def _purge_expired(self) -> None:
        """Drop all expired entries."""
        now = time.time()
        stale = [k for k, v in self._store.items() if (now - v.created_at) >= v.ttl]
        for k in stale:
            del self._store[k]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, sandbox_name: str) -> dict[str, Any] | None:
        """Return cached state for *sandbox_name*, or ``None`` if missing / expired.

        A cache hit returns immediately with no disk I/O.
        """
        with self._lock:
            entry = self._store.get(sandbox_name)
            if entry is None:
                self.misses += 1
                return None
            if not entry.is_valid:
                del self._store[sandbox_name]
                self.misses += 1
                return None
            self._touch(sandbox_name)
            self.hits += 1
            return entry.data

    def set(self, sandbox_name: str, state: dict[str, Any],
            ttl_seconds: float | None = None) -> None:
        """Store *state* for *sandbox_name*.

        Parameters
        ----------
        sandbox_name:
            Sandbox identifier.
        state:
            Full state dict (as returned by ``SandboxState.load()``).
        ttl_seconds:
            Override the default TTL for this entry.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        with self._lock:
            self._purge_expired()
            self._evict_lru()
            if sandbox_name in self._store:
                self._store.move_to_end(sandbox_name)
            self._store[sandbox_name] = CacheEntry(data=state, ttl=ttl)

    def invalidate(self, sandbox_name: str | None = None) -> None:
        """Invalidate one or all cached entries.

        Parameters
        ----------
        sandbox_name:
            Drop only this entry.  Pass ``None`` to clear the entire cache.
        """
        with self._lock:
            if sandbox_name is None:
                self._store.clear()
            else:
                self._store.pop(sandbox_name, None)

    def invalidate_stale(self) -> int:
        """Purge all expired entries and return the number removed."""
        with self._lock:
            now = time.time()
            stale = [k for k, v in self._store.items() if (now - v.created_at) >= v.ttl]
            for k in stale:
                del self._store[k]
            return len(stale)

    def batch_load(
        self,
        sandbox_names: list[str],
        *,
        loader: "SandboxState | None" = None,
        base_paths: "dict[str, Path] | None" = None,
    ) -> dict[str, dict[str, Any]]:
        """Load multiple sandboxes, using cache where valid.

        Disk reads happen only for cache misses.  Every requested name
        is guaranteed to appear in the result.

        Parameters
        ----------
        sandbox_names:
            List of sandbox names to load.
        loader:
            Optional pre-constructed ``SandboxState`` to reuse for all
            cache-miss reads.  When ``None`` a new ``SandboxState`` is
            created per name using the default ``SANDBOX_DIR`` or
            *base_paths*.
        base_paths:
            Optional mapping of ``name → Path`` used when constructing
            ``SandboxState`` for cache-miss names.  Useful in tests.

        Returns
        -------
        dict[str, dict[str, Any]]
            ``{sandbox_name: state_dict}`` — every requested name present.
        """
        with self._lock:
            self._purge_expired()
            result: dict[str, dict[str, Any]] = {}
            to_load: list[str] = []
            for name in sandbox_names:
                entry = self._store.get(name)
                if entry is not None and entry.is_valid:
                    self._touch(name)
                    self.hits += 1
                    result[name] = entry.data
                else:
                    if name in self._store:
                        del self._store[name]
                    self.misses += 1
                    to_load.append(name)

        # I/O outside the lock so other callers aren't blocked.
        if to_load:
            from hero.state.sandbox import SandboxState  # lazy — avoids circular import
            for name in to_load:
                if loader is not None:
                    ss: SandboxState = loader
                elif base_paths and name in base_paths:
                    ss = SandboxState(name, base_path=base_paths[name])
                else:
                    ss = SandboxState(name)
                state_data = ss.load()
                with self._lock:
                    self._evict_lru()
                    self._store[name] = CacheEntry(data=state_data, ttl=self.default_ttl)
                result[name] = state_data

        return result

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Number of valid (non-expired) entries."""
        with self._lock:
            self._purge_expired()
            return len(self._store)

    def stats(self) -> dict[str, Any]:
        """Cache statistics for observability."""
        with self._lock:
            self._purge_expired()
            total = self.hits + self.misses
            hit_rate = (self.hits / total) if total else 0.0
            return {
                "entries": len(self._store),
                "valid": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": round(hit_rate, 4),
                "ttl": self.default_ttl,
                "maxsize": self.maxsize,
                "keys": list(self._store.keys()),
            }

    def clear_stats(self) -> None:
        """Reset hit / miss / eviction counters."""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def __len__(self) -> int:
        return self.size

    def __contains__(self, sandbox_name: str) -> bool:
        with self._lock:
            entry = self._store.get(sandbox_name)
            return bool(entry is not None and entry.is_valid)

    def __repr__(self) -> str:  # pragma: no cover
        s = self.stats()
        return (
            f"StateCache(entries={s['entries']}, "
            f"hits={s['hits']}, "
            f"misses={s['misses']}, "
            f"hit_rate={s['hit_rate']})"
        )


# ---------------------------------------------------------------------------
# Module-level convenience singleton
# ---------------------------------------------------------------------------

#: Default shared cache used by commands that do not need isolation.
default_cache: StateCache = StateCache()
