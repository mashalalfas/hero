"""Analysis cache — memoize expensive analyzer results (flutter analyze, tsc, npm lint).

Cache key: hash of (sandbox_path, analyzer_command, source_file_mtimes).
TTL: 60 seconds (configurable).

This avoids re-running analyzers on every `hero go` when nothing changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".hero" / "cache" / "analysis"
DEFAULT_TTL = 60  # seconds


def _hash_paths(paths: list[Path]) -> str:
    """Create a hash from file modification times for a list of paths."""
    h = hashlib.sha256()
    for p in sorted(paths):
        try:
            h.update(str(p).encode())
            h.update(str(p.stat().st_mtime).encode())
        except OSError:
            h.update(b"missing")
    return h.hexdigest()[:16]


def _cache_key(sandbox_path: Path, analyze_cmd: list[str],
               source_globs: list[str] | None = None) -> str:
    """Build a cache key from sandbox path + command + source file hashes."""
    key_parts = f"{sandbox_path}:{':'.join(analyze_cmd)}"

    if source_globs:
        source_files = []
        for pattern in source_globs:
            matches = list(sandbox_path.glob(pattern))
            source_files.extend(matches)
        source_hash = _hash_paths(source_files)
        key_parts += f":{source_hash}"

    return hashlib.sha256(key_parts.encode()).hexdigest()[:16]


def get_cached(sandbox_path: Path, analyze_cmd: list[str],
               source_globs: list[str] | None = None,
               ttl: int = DEFAULT_TTL) -> dict[str, Any] | None:
    """Return cached analysis result if fresh, else None.

    Parameters
    ----------
    sandbox_path: Root of the project.
    analyze_cmd: The analyzer command that was run.
    source_globs: Glob patterns for source files to track for invalidation.
    ttl: Time-to-live in seconds (default 60).

    Returns
    -------
    Cached result dict or None if missing/expired.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(sandbox_path, analyze_cmd, source_globs)
    cache_file = CACHE_DIR / f"{key}.json"

    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Check TTL
    if time.time() - data.get("cached_at", 0) > ttl:
        cache_file.unlink(missing_ok=True)
        return None

    return data


def set_cached(sandbox_path: Path, analyze_cmd: list[str],
               result: dict[str, Any],
               source_globs: list[str] | None = None) -> None:
    """Write analysis result to cache.

    Parameters
    ----------
    sandbox_path: Root of the project.
    analyze_cmd: The analyzer command that was run.
    result: The analysis result to cache.
    source_globs: Glob patterns for source files tracked for invalidation.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(sandbox_path, analyze_cmd, source_globs)
    cache_file = CACHE_DIR / f"{key}.json"

    payload = {
        "cached_at": time.time(),
        "sandbox": str(sandbox_path),
        "command": analyze_cmd,
        "result": result,
    }
    cache_file.write_text(json.dumps(payload, indent=2))


def invalidate(sandbox_path: Path | None = None) -> int:
    """Invalidate cache entries.

    Parameters
    ----------
    sandbox_path: If given, only invalidate entries for this sandbox.
                  If None, clear the entire cache.

    Returns
    -------
    Number of entries removed.
    """
    if not CACHE_DIR.exists():
        return 0

    if sandbox_path is None:
        removed = 0
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    sandbox_str = str(sandbox_path)
    removed = 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("sandbox") == sandbox_str:
                f.unlink()
                removed += 1
        except (json.JSONDecodeError, OSError):
            pass
    return removed


def cached_analyze(analyze_cmd: list[str], cwd: Path,
                   source_globs: list[str] | None = None,
                   ttl: int = DEFAULT_TTL) -> dict[str, Any]:
    """Run analysis with caching.

    Checks cache first. On miss, runs the subprocess and caches the result.

    Parameters
    ----------
    analyze_cmd: Command to run (e.g. ['flutter', 'analyze']).
    cwd: Working directory.
    source_globs: Source file patterns to track for invalidation.
    ttl: Cache TTL in seconds.

    Returns
    -------
    Analysis result dict with keys: success, exit_code, output, cached (bool).
    """
    cached = get_cached(cwd, analyze_cmd, source_globs, ttl)
    if cached is not None:
        return {**cached["result"], "cached": True, "cached_at": cached["cached_at"]}

    # Cache miss — run the analysis
    try:
        result = subprocess.run(
            analyze_cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        analysis_result = {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "output": output[:2000],
        }
    except subprocess.TimeoutExpired:
        analysis_result = {"success": False, "exit_code": -1, "output": "timed out"}
    except FileNotFoundError:
        analysis_result = {"success": False, "exit_code": -2, "output": "command not found"}

    set_cached(cwd, analyze_cmd, analysis_result, source_globs)
    return {**analysis_result, "cached": False}
