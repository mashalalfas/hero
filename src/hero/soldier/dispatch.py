"""Dispatch queue — connects HERO CLI to OpenClaw sessions_spawn.

When hero spawn/deploy is called, tasks are written to ~/.hero/dispatch/.
The OpenClaw agent reads these and executes via sessions_spawn with
the correct model per task (unlike Hermes which ignores model overrides).

Each task includes all fields needed for a sessions_spawn call:
- model: provider/model format for OpenClaw
- label: descriptive identifier
- task: the actual prompt with file paths
- timeout: runTimeoutSeconds
- context_window: for context budget estimation
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.logging import get_logger

_logger = get_logger("dispatch")

DISPATCH_DIR = Path.home() / ".hero" / "dispatch"


def _ensure_dir() -> None:
    """Create dispatch directory if it doesn't exist."""
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)


def enqueue(
    sandbox: str,
    task: str,
    role: str = "soldier",
    model: str = "",
    model_short: str = "",
    budget: int = 5000,
    workdir: str = "",
    timeout: int = 600,
    label: str = "",
    max_tokens: int = 8000,
    context_window: int = 131072,
) -> str:
    """Write a task to the dispatch queue for OpenClaw execution.

    Returns the task_id (UUID prefix).
    """
    _ensure_dir()

    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    entry = {
        "task_id": task_id,
        "sandbox": sandbox,
        "workdir": workdir or f"/home/max/Development/Taurus/{sandbox}",
        "label": label or f"{sandbox}-{role}",
        "model": model,        # OpenClaw format: "provider/model"
        "role": role,
        "task": task,
        "timeout": timeout,    # runTimeoutSeconds for sessions_spawn
        "max_tokens": max_tokens,
        "context_window": context_window,
        "budget": budget,
        "status": "pending",   # pending | running | completed | failed
        "created_at": now,
        "dispatched_at": None,
        "completed_at": None,
        "result": None,
    }

    # Write as TOON — more compact than JSON, ~37% token savings
    _write_toon_entry(task_id, entry)
    return task_id


def _write_toon_entry(task_id: str, entry: dict) -> None:
    """Write a dispatch entry as a .toon file.

    Format is compact key: value pairs for token efficiency.
    Lists and multiline values are handled explicitly.
    """
    task_file = DISPATCH_DIR / f"{task_id}.toon"
    lines = []
    for k, v in entry.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, str):
            # Escape quotes and handle multiline
            if "\n" in v:
                # Multiline string — use quoted block
                lines.append(f"{k}: |")
                for line in v.split("\n"):
                    lines.append(f"  {line}")
            else:
                escaped = v.replace('"', '\\"')
                lines.append(f'{k}: "{escaped}"')
        elif isinstance(v, list):
            items = ", ".join(str(x) for x in v)
            lines.append(f"{k}[{len(v)}]: {items}")
        else:
            lines.append(f"{k}: {v}")
    task_file.write_text("\n".join(lines) + "\n")


def _read_task_file(task_id: str) -> dict | None:
    """Read a task file by ID, trying .toon first then .json for backward compat."""
    # Try .toon first (new format)
    toon_file = DISPATCH_DIR / f"{task_id}.toon"
    if toon_file.exists():
        try:
            data = _parse_toon_file(toon_file.read_text())
            if data:
                return data
        except Exception:
            pass
    # Fallback to .json (old format)
    json_file = DISPATCH_DIR / f"{task_id}.json"
    if json_file.exists():
        try:
            return json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_task_file(task_id: str, data: dict) -> None:
    """Write a task file as TOON (.toon)."""
    _write_toon_entry(task_id, data)
    # Clean up old .json if it exists
    old_json = DISPATCH_DIR / f"{task_id}.json"
    if old_json.exists():
        old_json.unlink()


def _iter_task_files() -> list[Path]:
    """Iterate all task files (.toon and legacy .json), sorted by name."""
    all_files = sorted(DISPATCH_DIR.glob("*.toon"))
    all_files.extend(sorted(DISPATCH_DIR.glob("*.json")))
    # Deduplicate: if both .toon and .json exist for same task_id, prefer .toon
    seen: set[str] = set()
    unique: list[Path] = []
    for f in all_files:
        tid = f.stem  # filename without extension
        if tid not in seen:
            seen.add(tid)
            unique.append(f)
    return unique


def _load_task_from_file(f: Path) -> dict | None:
    """Load a task dict from either .toon or .json file."""
    try:
        if f.suffix == ".toon":
            data = _parse_toon_file(f.read_text())
            return data
        else:
            return json.loads(f.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _parse_toon_file(content: str) -> dict | None:
    """Parse a TOON-format dispatch entry into a dict.

    Format:
        key: value
        key: "quoted string"
        key: null
        key: |
          multiline
          content
        key[N]: val1, val2
    """
    result: dict = {}
    current_key = None
    current_multiline: list[str] = []
    in_multiline = False

    for line in content.split("\n"):
        stripped = line.rstrip()

        if in_multiline:
            if stripped.startswith("  "):
                current_multiline.append(stripped[2:])
                continue
            else:
                # End of multiline
                result[current_key] = "\n".join(current_multiline)
                current_multiline = []
                in_multiline = False
                current_key = None
                if not stripped:
                    continue

        if not stripped:
            continue

        # Check for key[N]: list format
        list_match = re.match(r"^(\w+)\[(\d+)\]:\s*(.*)$", stripped)
        if list_match:
            key, _count, values_str = list_match.groups()
            if values_str.strip():
                result[key] = [_parse_toon_value(v.strip()) for v in values_str.split(",")]
            else:
                result[key] = []
            continue

        # Check for key: | multiline
        multiline_match = re.match(r"^(\w+):\s*\|$", stripped)
        if multiline_match:
            current_key = multiline_match.group(1)
            in_multiline = True
            current_multiline = []
            continue

        # Check for key: value
        kv_match = re.match(r"^(\w+):\s*(.*)$", stripped)
        if kv_match:
            key, value = kv_match.group(1), kv_match.group(2).strip()
            result[key] = _parse_toon_value(value)
            continue

    # Handle multiline at end of file
    if in_multiline and current_key:
        result[current_key] = "\n".join(current_multiline)

    return result if result else None


def _parse_toon_value(value: str) -> Any:
    """Parse a single TOON value."""
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    # Quoted string
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"')
    # Number
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    return value


def list_pending() -> list[dict]:
    """List all pending tasks in the dispatch queue."""
    _ensure_dir()
    pending = []
    for f in _iter_task_files():
        data = _load_task_from_file(f)
        if data and data.get("status") == "pending":
            pending.append(data)
    return pending


def list_all() -> list[dict]:
    """List all tasks in the dispatch queue (any status)."""
    _ensure_dir()
    tasks = []
    for f in _iter_task_files():
        data = _load_task_from_file(f)
        if data:
            tasks.append(data)
    return tasks


def get_task(task_id: str) -> dict | None:
    """Get a specific task by ID."""
    return _read_task_file(task_id)


def mark_dispatched(task_id: str) -> None:
    """Mark a task as dispatched (being executed)."""
    data = _read_task_file(task_id)
    if data:
        data["status"] = "dispatched"
        data["dispatched_at"] = datetime.now().isoformat()
        _write_task_file(task_id, data)


def mark_completed(task_id: str, result: str = "") -> None:
    """Mark a task as completed. Also writes per-agent status file.

    The dispatch .toon/.json file is updated in-place and then deleted so
    completed tasks don't pile up as stale state. A separate durable status
    record is written to ~/.hero/status/<task_id>.json so the parent can
    poll results without contending on the session file.
    """
    data = _read_task_file(task_id)
    if data:
        data["status"] = "completed"
        data["completed_at"] = datetime.now().isoformat()
        data["result"] = result
        _write_task_file(task_id, data)
        _delete_task_file(task_id)
        # Write per-agent status file — avoids session file contention
        from hero.state.status import write_status
        write_status(task_id, {
            "task_id": task_id,
            "sandbox": data.get("sandbox", "unknown"),
            "status": "completed",
            "result": result,
            "stage": data.get("stage", ""),
        })


def mark_failed(task_id: str, error: str = "") -> None:
    """Mark a task as failed, send to DLQ, then remove its dispatch file.

    The dispatch .toon/.json file is deleted after the status is persisted
    and the entry has been sent to the Dead Letter Queue, so failed tasks
    don't pile up as stale state.
    """
    data = _read_task_file(task_id)
    if data:
        data["status"] = "failed"
        data["completed_at"] = datetime.now().isoformat()
        data["result"] = error
        _write_task_file(task_id, data)
        # Persist to DLQ BEFORE deleting the file so failure data is never lost
        from hero.reliability.dlq import send_to_dlq  # noqa: F811

        sandbox = data.get("sandbox", "")
        _logger.info(
            "Sending failed task to DLQ",
            task_id=task_id,
            sandbox=sandbox,
            error=error,
        )
        send_to_dlq(task_id, data, error)
        _delete_task_file(task_id)


def purge_stale(age_hours: int = 24) -> int:
    """Remove dispatch task files older than age_hours.

    Tasks in pending/dispatched status that never completed are stale.
    Returns count of files removed.
    """
    import time

    now = time.time()
    cutoff = now - (age_hours * 3600)
    purged = 0
    for f in _iter_task_files():
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            try:
                f.unlink()
                purged += 1
            except OSError:
                pass
    return purged


def clear_completed() -> int:
    """Remove completed/failed tasks. Returns count removed."""
    _ensure_dir()
    removed = 0
    for f in _iter_task_files():
        data = _load_task_from_file(f)
        if data and data.get("status") in ("completed", "failed"):
            f.unlink()
            removed += 1
    return removed


def get_sessions_spawn_command(task: dict) -> dict:
    """Convert a dispatch task to OpenClaw sessions_spawn parameters.
    
    Returns a dict that can be passed directly to sessions_spawn tool.
    """
    return {
        "label": task.get("label", f"{task['sandbox']}-{task['role']}"),
        "model": task["model"],
        "mode": "run",
        "runtime": "subagent",
        "runTimeoutSeconds": task.get("timeout", 600),
        "task": _build_task_prompt(task),
    }


def _delete_task_file(task_id: str) -> None:
    """Remove both .toon and .json dispatch files for a task."""
    for ext in (".toon", ".json"):
        f = DISPATCH_DIR / f"{task_id}{ext}"
        if f.exists():
            f.unlink(missing_ok=True)


def _build_task_prompt(task: dict) -> str:
    """Build a complete task prompt using external .md templates.

    Loads role-specific template from ~/.hero/prompts/roles/{role}.md
    (or bundled defaults). Falls back to soldier template if role template
    is not found.
    """
    from hero.prompts import load_rule, render_template

    role = task["role"]
    context_window = task.get("context_window", 131072)
    max_tokens = task.get("max_tokens", 8000)
    budget = task.get("budget", 5000)

    template_path = f"roles/{role}.md"
    try:
        prompt = render_template(
            template_path,
            sandbox=task["sandbox"],
            workdir=task["workdir"],
            model=task["model"],
            context_window=context_window,
            max_tokens=max_tokens,
            budget=budget,
            task=task["task"],
            extra_rules=load_rule("context-budget"),
        )
    except FileNotFoundError:
        prompt = render_template(
            "roles/soldier.md",
            sandbox=task["sandbox"],
            workdir=task["workdir"],
            model=task["model"],
            context_window=context_window,
            max_tokens=max_tokens,
            budget=budget,
            task=task["task"],
            extra_rules=load_rule("context-budget"),
        )
    return prompt