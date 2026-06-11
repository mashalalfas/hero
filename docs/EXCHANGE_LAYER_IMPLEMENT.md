# Exchange Layer — Implementation Brief

> **Date:** 2026-06-07  
> **Purpose:** Concise step-by-step implementation guide for an implementation agent  
> **Parent Spec:** `docs/EXCHANGE_LAYER_SPEC.md`  
> **Estimated effort:** 3-4 implementation sessions

---

## Overview

Build an inter-agent message bus (Exchange Layer) for the HERO CLI system at `/home/max/Development/HERO/`. Messages are `.toon` files under `~/.hero/exchange/`. The bus uses the same file patterns as the existing dispatch queue.

**Key constraint:** All existing functionality must remain unchanged when `--exchange` flag is NOT passed. Exchange is entirely opt-in.

## 🚨 Critical: Context Window Guardrails

Without these, the Lead's context balloons and soldiers drown in message noise.

### Guardrail 1: Lead is NOT in the message path

The Lead's only job regarding Exchange is:
- `create_channel()` — one-time, tiny
- Poll `TASKS.toon` for aggregate status (is everything done? Y/N)

Messages flow **soldier → .toon file → soldier**. The Lead never touches individual `msg_*.toon` files. If the Lead needs to know something, the soldier writes it to a file the Lead reads — the Lead doesn't CC itself on every message.

### Guardrail 2: No CC pattern

Messages have ONE recipient. No `cc_lead: true` flag. If a soldier needs to notify the Lead, it writes a status update to its own status file. The Lead reads only:
- `CHANNEL.toon` — soldier roster + aggregate status
- `TASKS.toon` — task progress summary
- Individual soldier status files IF something goes wrong (on-demand)

### Guardrail 3: listen() has a batch limit

`listen()` NEVER returns all messages at once:

```python
def listen(self, for_sandbox, for_role, max_results=5, priority_min="normal"):
    """Return up to max_results messages, filtered by priority."""
```

Priority chain: critical → high → normal → low. A soldier polls, gets the top 5 by priority, processes them, then polls again. Keeps context injection small and predictable.

### Guardrail 4: Per-soldier assignment file

Instead of scanning the whole TASKS.toon to find one's work, the Lead writes a single file per soldier when creating the exchange:

```
~/.hero/exchange/<deploy_id>/assignments/<soldier_id>.toon
# Content:
my_task: "task_002"
my_role: "developer"
input_from: "task_001"
output_to: "task_003"
```

Soldier reads ONE file to understand its role. No need to parse the entire task list.

### Guardrail 5: Archive consumed messages

`mark_read()` doesn't just update status — it moves the message file:

```python
def mark_read(self, msg_id):
    # move from messages/ to messages/archive/
    shutil.move(msg_path, archive_path)
```

Soldiers never re-read stale messages. Every poll returns only what's actually new.

---

## File Path Reference

All paths relative to `/home/max/Development/HERO/` unless absolute.

### Files to CREATE

| # | File | What it does |
|---|------|-------------|
| 1 | `src/hero/exchange/__init__.py` | Package init; exports `ExchangeLayer` class |
| 2 | `src/hero/exchange/message.py` | `MailMessage` dataclass, TOON read/write |
| 3 | `src/hero/exchange/core.py` | Core ExchangeLayer: send(), listen(), mark_read(), roster |
| 4 | `src/hero/exchange/task_list.py` | Shared task list: post, list, claim (atomic), done, fail |
| 5 | `src/hero/exchange/pipe.py` | Result passing: push, pull, status |
| 6 | `src/hero/exchange/review.py` | Adversarial review: request, respond, status |
| 7 | `src/hero/exchange/reliability.py` | Retry backoff, TTL expiry, DLQ integration |
| 8 | `src/hero/exchange/lock.py` | Atomic file lock using `O_CREAT | O_EXCL` |
| 9 | `src/hero/commands/exchange.py` | CLI: `hero exchange send|listen|broadcast|status` etc. |

### Files to MODIFY

| # | File | Change |
|---|------|--------|
| A | `src/hero/cli.py` | Register `exchange` command group |
| B | `src/hero/commands/deploy.py` | Add `--exchange` flag + roster registration |
| C | `src/hero/commands/spawn.py` | Add `--exchange` flag |
| D | `src/hero/commands/go.py` | Add `--exchange` flag + channel creation |
| E | `src/hero/soldier/spawner.py` | Register soldier in roster on launch |
| F | `src/hero/soldier/context.py` | Inject exchange context block when enabled |
| G | `src/hero/reliability/dlq.py` | Accept exchange messages in DLQ |
| H | `src/hero/state/status.py` | Write exchange status updates |
| I | `~/.hero/army.yaml` | Add `exchange_enabled: true/false` per role (optional) |

---

## Step-by-Step Implementation

### Step 1: Message Data Model (`exchange/message.py`)

```python
"""MailMessage dataclass + TOON serialization for Exchange Layer."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

EXCHANGE_DIR = Path.home() / ".hero" / "exchange"

# Message types
MSG_TYPE_DIRECT = "direct"
MSG_TYPE_BROADCAST = "broadcast"
MSG_TYPE_TASK_OFFER = "task_offer"
MSG_TYPE_TASK_CLAIM = "task_claim"
MSG_TYPE_TASK_STATUS = "task_status"
MSG_TYPE_PIPE_RESULT = "pipe_result"
MSG_TYPE_REVIEW_REQUEST = "review_request"
MSG_TYPE_REVIEW_RESPONSE = "review_response"
ALL_MSG_TYPES = frozenset({
    MSG_TYPE_DIRECT, MSG_TYPE_BROADCAST, MSG_TYPE_TASK_OFFER,
    MSG_TYPE_TASK_CLAIM, MSG_TYPE_TASK_STATUS, MSG_TYPE_PIPE_RESULT,
    MSG_TYPE_REVIEW_REQUEST, MSG_TYPE_REVIEW_RESPONSE,
})

# Statuses
STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_READ = "read"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"

# Task list specific statuses
TASK_STATUS_AVAILABLE = "available"
TASK_STATUS_CLAIMED = "claimed"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# Priority levels
PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"
ALL_PRIORITIES = frozenset({PRIORITY_LOW, PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_CRITICAL})


@dataclass
class MailMessage:
    """A single exchange message."""
    msg_id: str = ""
    msg_type: str = MSG_TYPE_DIRECT
    status: str = STATUS_PENDING
    from_role: str = ""
    from_sandbox: str = ""
    from_model: str = ""
    to_role: str = ""
    to_sandbox: str = ""
    to_target: str = ""
    body: str = ""
    created_at: str = ""
    ttl_seconds: int = 3600
    delivery_attempts: int = 0
    last_attempt: Optional[str] = None
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    priority: str = PRIORITY_NORMAL

    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_expired(self) -> bool:
        """Check if message TTL has expired."""
        if not self.created_at:
            return False
        try:
            created = datetime.fromisoformat(self.created_at)
            now = datetime.now(timezone.utc)
            elapsed = (now - created).total_seconds()
            return elapsed > self.ttl_seconds
        except (ValueError, TypeError):
            return False

    @classmethod
    def from_toon(cls, path: Path) -> Optional["MailMessage"]:
        """Parse a TOON file into a MailMessage."""
        # Reuse hero.soldier.dispatch._parse_toon_file or inline parser
        from hero.soldier.dispatch import _parse_toon_file
        data = _parse_toon_file(path.read_text())
        if not data:
            return None
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def to_toon(self) -> str:
        """Serialize to TOON format string."""
        lines = []
        for field_name in (
            "msg_id", "msg_type", "status", "from_role", "from_sandbox",
            "from_model", "to_role", "to_sandbox", "to_target",
            "created_at", "ttl_seconds", "delivery_attempts",
            "last_attempt", "reply_to", "correlation_id", "priority",
        ):
            val = getattr(self, field_name, None)
            if val is None:
                lines.append(f"{field_name}: null")
            elif isinstance(val, bool):
                lines.append(f"{field_name}: {'true' if val else 'false'}")
            elif isinstance(val, (int, float)):
                lines.append(f"{field_name}: {val}")
            elif isinstance(val, str):
                if "\n" in val:
                    lines.append(f"{field_name}: |")
                    for vline in val.split("\n"):
                        lines.append(f"  {vline}")
                else:
                    escaped = val.replace('"', '\\"')
                    lines.append(f'{field_name}: "{escaped}"')
            else:
                lines.append(f"{field_name}: {val}")

        # Body is always last (potentially multiline)
        body_val = self.body or ""
        if "\n" in body_val:
            lines.append("body: |")
            for bline in body_val.split("\n"):
                lines.append(f"  {bline}")
        else:
            escaped = body_val.replace('"', '\\"')
            lines.append(f'body: "{escaped}"')

        return "\n".join(lines) + "\n"
```

**Subdirectory helpers:**

```python
# Message directory routing
MSG_DIR_MAP = {
    MSG_TYPE_DIRECT: "direct",
    MSG_TYPE_BROADCAST: "broadcast",
    MSG_TYPE_TASK_OFFER: "task_list",
    MSG_TYPE_TASK_CLAIM: "task_list",
    MSG_TYPE_TASK_STATUS: "task_list",
    MSG_TYPE_PIPE_RESULT: "result_pipe",
    MSG_TYPE_REVIEW_REQUEST: "review",
    MSG_TYPE_REVIEW_RESPONSE: "review",
}


def get_msg_dir(msg_type: str) -> Path:
    sub = MSG_DIR_MAP.get(msg_type, "direct")
    return EXCHANGE_DIR / sub


def msg_file_path(msg_id: str, msg_type: str) -> Path:
    return get_msg_dir(msg_type) / f"{msg_id}.toon"


def iter_messages(msg_type: str | None = None) -> list[Path]:
    """Iterate all message files, optionally filtered by type."""
    if msg_type:
        subs = [MSG_DIR_MAP.get(msg_type, "direct")]
    else:
        subs = set(MSG_DIR_MAP.values())
    files = []
    for sub in subs:
        d = EXCHANGE_DIR / sub
        if d.exists():
            files.extend(sorted(d.glob("*.toon")))
    return files
```

---

### Step 2: Lock (`exchange/lock.py`)

```python
"""Atomic file-based lock using O_CREAT | O_EXCL."""

import os
import time
from pathlib import Path

LOCK_DIR = Path.home() / ".hero" / "exchange" / "lock"
DEFAULT_TTL = 300  # 5 minutes


def acquire_lock(name: str, ttl: int = DEFAULT_TTL) -> bool:
    """Try to acquire a named lock. Returns True if acquired."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / name
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        # Check if lock is stale
        try:
            age = time.time() - lock_path.stat().st_mtime
            if age > ttl:
                lock_path.unlink(missing_ok=True)
                # Retry once
                try:
                    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    return True
                except FileExistsError:
                    return False
        except OSError:
            pass
        return False


def release_lock(name: str) -> None:
    """Release a named lock."""
    lock_path = LOCK_DIR / name
    lock_path.unlink(missing_ok=True)


def is_locked(name: str) -> bool:
    """Check if a lock exists and is not stale."""
    lock_path = LOCK_DIR / name
    if not lock_path.exists():
        return False
    try:
        age = time.time() - lock_path.stat().st_mtime
        if age > DEFAULT_TTL:
            lock_path.unlink(missing_ok=True)
            return False
        return True
    except OSError:
        return False
```

---

### Guardrail 6: Soldier uses assignment file, not task list scan

When a soldier spawns, it reads its assignment file (Guardrail 4), not the full TASKS.toon. The assignment tells it exactly:
- Which task to work on
- Where input comes from
- Where output goes

This means the soldier never even reads the shared task list unless explicitly told to.

### Step 3: Core Exchange Layer (`exchange/core.py`)

This is the main module. It implements `ExchangeLayer`, the primary programmatic API.

```python
"""Core ExchangeLayer class — send, listen, mark_read, roster."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hero.exchange.message import (
    MailMessage, EXCHANGE_DIR, MSG_DIR_MAP,
    MSG_TYPE_DIRECT, MSG_TYPE_BROADCAST,
    STATUS_PENDING, STATUS_DELIVERED, STATUS_READ, STATUS_FAILED,
    PRIORITY_NORMAL, ALL_PRIORITIES,
    get_msg_dir, msg_file_path, iter_messages,
)
from hero.exchange.reliability import check_ttl_and_auto_expire
from hero.state.status import write_status

EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)

# Roster
ROSTER_PATH = EXCHANGE_DIR / "roster.toon"
CONFIG_PATH = EXCHANGE_DIR / "config.toon"


class ExchangeLayer:
    """Primary API for the Exchange Layer message bus."""

    def send(
        self,
        to_sandbox: str,
        body: str,
        to_role: str = "",
        msg_type: str = MSG_TYPE_DIRECT,
        priority: str = PRIORITY_NORMAL,
        ttl_seconds: int = 3600,
        reply_to: str | None = None,
        correlation_id: str | None = None,
        from_role: str = "",
        from_sandbox: str = "",
        from_model: str = "",
    ) -> str:
        """Send a message. Returns msg_id."""
        msg = MailMessage(
            msg_type=msg_type,
            from_role=from_role,
            from_sandbox=from_sandbox,
            from_model=from_model,
            to_role=to_role,
            to_sandbox=to_sandbox,
            to_target=to_sandbox,
            body=body,
            ttl_seconds=ttl_seconds,
            reply_to=reply_to,
            correlation_id=correlation_id,
            priority=priority if priority in ALL_PRIORITIES else PRIORITY_NORMAL,
        )
        self._write(msg)
        write_status(msg.msg_id, {
            "exchange_msg_id": msg.msg_id,
            "type": msg.msg_type,
            "from": f"{msg.from_sandbox}:{msg.from_role}",
            "to": f"{msg.to_sandbox}:{msg.to_role}",
            "status": STATUS_PENDING,
        })
        return msg.msg_id

    def broadcast(
        self,
        body: str,
        role_filter: str | None = None,
        sandbox_filter: str | None = None,
        priority: str = PRIORITY_NORMAL,
        ttl_seconds: int = 3600,
        correlation_id: str | None = None,
        from_role: str = "",
        from_sandbox: str = "",
        from_model: str = "",
    ) -> str:
        """Broadcast to all active soldiers (optionally filtered)."""
        roster = self._load_roster()
        recipients = []
        for entry in roster:
            if role_filter and entry.get("role") != role_filter:
                continue
            if sandbox_filter and entry.get("sandbox") != sandbox_filter:
                continue
            if entry.get("status") == "running":
                recipients.append(entry)

        msg = MailMessage(
            msg_type=MSG_TYPE_BROADCAST,
            from_role=from_role,
            from_sandbox=from_sandbox,
            from_model=from_model,
            to_target="*",
            body=body,
            ttl_seconds=ttl_seconds,
            correlation_id=correlation_id,
            priority=priority,
        )
        self._write(msg)
        return msg.msg_id

    def listen(
        self,
        for_sandbox: str = "",
        for_role: str = "",
        msg_type: str | None = None,
        include_delivered: bool = False,
        max_results: int = 5,
        priority_min: str = "low",
    ) -> list[MailMessage]:
        """Return messages addressed to this soldier.

        Returns pending messages by default, capped at max_results.
        If include_delivered=True, also returns delivered-not-read messages.

        Guardrail: max_results=5 prevents context flooding.
        Guardrail: priority_min filters out low-priority noise.
        """
        # First, auto-expire stale messages
        check_ttl_and_auto_expire()

        messages: list[MailMessage] = []
        for path in iter_messages(msg_type):
            msg = MailMessage.from_toon(path)
            if msg is None:
                continue

            # Check if addressed to us
            if for_sandbox and for_sandbox not in (msg.to_sandbox, "") and msg.to_target not in ("*", for_sandbox):
                continue
            if for_role and for_role not in (msg.to_role, "") and msg.to_target not in ("*",):
                continue

            # Status filter
            if msg.status == STATUS_PENDING:
                messages.append(msg)
            elif include_delivered and msg.status == STATUS_DELIVERED:
                messages.append(msg)

        # Sort: critical first, then high, then normal, then low; then oldest first
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        priority_min_order = priority_order.get(priority_min, 2)
        messages = [m for m in messages if priority_order.get(m.priority, 2) <= priority_min_order]
        messages.sort(key=lambda m: (priority_order.get(m.priority, 2), m.created_at))

        # Cap at max_results (Guardrail 3)
        messages = messages[:max_results]

        # Mark as delivered
        for msg in messages:
            if msg.status == STATUS_PENDING:
                msg.status = STATUS_DELIVERED
                self._write(msg)

        return messages

    def mark_read(self, msg_id: str) -> bool:
        """Mark a message as read. Returns True if found.

        Guardrail 5: Archives the message so soldiers never re-read stale data.
        """
        for path in iter_messages():
            if path.stem == msg_id:
                msg = MailMessage.from_toon(path)
                if msg:
                    msg.status = STATUS_READ
                    msg.delivery_attempts += 1
                    # Guardrail 5: archive instead of updating in place
                    archive_path = self._archive(msg_id)
                    return archive_path is not None
        return False

    def get_message(self, msg_id: str) -> MailMessage | None:
        """Retrieve a specific message by ID."""
        for path in iter_messages():
            if path.stem == msg_id:
                return MailMessage.from_toon(path)
        return None

    # ── Roster management ───────────────────────────────────

    def register_soldier(
        self,
        sandbox: str,
        soldier_id: str,
        role: str = "soldier",
        model: str = "",
    ) -> None:
        """Register a soldier in the active roster."""
        roster = self._load_roster()
        # Remove any existing entry for this soldier
        roster = [e for e in roster if e.get("soldier_id") != soldier_id]
        roster.append({
            "sandbox": sandbox,
            "soldier_id": soldier_id,
            "role": role,
            "model": model,
            "status": "running",
            "spawned_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 600,
        })
        self._save_roster(roster)

    def unregister_soldier(self, soldier_id: str) -> None:
        """Remove a soldier from the active roster."""
        roster = self._load_roster()
        roster = [e for e in roster if e.get("soldier_id") != soldier_id]
        self._save_roster(roster)

    def get_roster(self) -> list[dict]:
        """Get the current active roster."""
        return self._load_roster()

    # ── Internal ────────────────────────────────────────────

    def _write(self, msg: MailMessage) -> None:
        """Atomically write a message file."""
        subdir = get_msg_dir(msg.msg_type)
        subdir.mkdir(parents=True, exist_ok=True)
        dest = subdir / f"{msg.msg_id}.toon"
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(msg.to_toon())
        tmp.replace(dest)

    def _archive(self, msg_id: str) -> Path | None:
        """Move a message file to archive/. Returns new path or None.

        Guardrail 5: Archive consumed messages so soldiers never re-read stale data.
        """
        for path in iter_messages():
            if path.stem == msg_id:
                archive_dir = EXCHANGE_DIR / "messages" / "archive"
                archive_dir.mkdir(parents=True, exist_ok=True)
                dest = archive_dir / path.name
                # Use rename (atomic on same filesystem)
                path.rename(dest)
                return dest
        return None

    def _load_roster(self) -> list[dict]:
        """Load roster from disk."""
        if not ROSTER_PATH.exists():
            return []
        from hero.soldier.dispatch import _parse_toon_file
        data = _parse_toon_file(ROSTER_PATH.read_text())
        if data and "entries" in data:
            return data["entries"]
        return []

    def _save_roster(self, entries: list[dict]) -> None:
        """Save roster to disk in TOON format."""
        out = ["# Active Soldier Roster — auto-populated on spawn\n"]
        out.append(f"last_updated: \"{datetime.now(timezone.utc).isoformat()}\"")
        out.append(f"count: {len(entries)}")
        out.append("entries:")
        for e in entries:
            out.append(f"  - sandbox: \"{e.get('sandbox', '')}\"")
            out.append(f"    soldier_id: \"{e.get('soldier_id', '')}\"")
            out.append(f"    role: \"{e.get('role', 'soldier')}\"")
            out.append(f"    model: \"{e.get('model', '')}\"")
            out.append(f"    status: \"{e.get('status', 'running')}\"")
            out.append(f"    spawned_at: \"{e.get('spawned_at', '')}\"")
            out.append(f"    ttl_seconds: {e.get('ttl_seconds', 600)}")
        ROSTER_PATH.write_text("\n".join(out) + "\n")
```

---

### Guardrail 4 Implementation: Per-Soldier Assignments

When creating an exchange with a task list, the Lead also writes individual assignment files:

```python
class Assignment:
    """Per-soldier assignment file. Guardrail 4: soldier reads ONE file, not the full task list."""

    @staticmethod
    def write_assignments(deploy_id: str, assignments: dict[str, dict]) -> None:
        """Write one assignment file per soldier.

        assignments: {
            "soldier_a": {
                "my_task": "task_001",
                "my_role": "developer",
                "input_from": "task_000",
                "output_to": "task_002"
            },
            ...
        }
        """
        assign_dir = EXCHANGE_DIR / deploy_id / "assignments"
        assign_dir.mkdir(parents=True, exist_ok=True)
        for soldier_id, data in assignments.items():
            path = assign_dir / f"{soldier_id}.toon"
            lines = [f"deploy_id: \"{deploy_id}\""]
            for k, v in data.items():
                if isinstance(v, str):
                    lines.append(f'{k}: "{v}"')
                else:
                    lines.append(f"{k}: {v}")
            path.write_text("\n".join(lines) + "\n")

    @staticmethod
    def read_assignment(deploy_id: str, soldier_id: str) -> dict | None:
        """Read this soldier's assignment file. Returns dict or None."""
        path = EXCHANGE_DIR / deploy_id / "assignments" / f"{soldier_id}.toon"
        if not path.exists():
            return None
        from hero.soldier.dispatch import _parse_toon_file
        return _parse_toon_file(path.read_text())

    @staticmethod
    def remove_assignments(deploy_id: str) -> None:
        """Clean up assignments when exchange is done."""
        assign_dir = EXCHANGE_DIR / deploy_id / "assignments"
        if assign_dir.exists():
            import shutil
            shutil.rmtree(assign_dir)
```

### Step 4: Task List (`exchange/task_list.py`)

```python
"""Shared task list with atomic claim locking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from hero.exchange.message import (
    MailMessage, MSG_TYPE_TASK_OFFER, MSG_TYPE_TASK_CLAIM, MSG_TYPE_TASK_STATUS,
    TASK_STATUS_AVAILABLE, TASK_STATUS_CLAIMED, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
    get_msg_dir, msg_file_path,
)
from hero.exchange.lock import acquire_lock, release_lock, is_locked
from hero.exchange.core import ExchangeLayer


class TaskList:
    """Shared task list for Lead → Workers pattern."""

    def __init__(self, xl: ExchangeLayer):
        self.xl = xl

    def post(
        self,
        title: str,
        description: str,
        files: list[str] | None = None,
        depends_on: list[str] | None = None,
        ttl_seconds: int = 7200,
        from_role: str = "lead",
        from_sandbox: str = "",
        from_model: str = "",
    ) -> str:
        """Post a task to the shared task list."""
        body_parts = [f"TITLE: {title}", "", description]
        if files:
            body_parts.append("")
            body_parts.append(f"FILES: {', '.join(files)}")
        if depends_on:
            body_parts.append("")
            body_parts.append(f"DEPENDS_ON: {', '.join(depends_on)}")
        body = "\n".join(body_parts)

        # We write a task_offer message with task-specific status field
        # Reuse the mail message but add task-specific metadata in body prefix
        return self.xl.send(
            to_sandbox="*",
            to_role="*",
            body=body,
            msg_type=MSG_TYPE_TASK_OFFER,
            ttl_seconds=ttl_seconds,
            correlation_id=None,
            from_role=from_role,
            from_sandbox=from_sandbox,
            from_model=from_model,
        )

    def list_available(self) -> list[dict]:
        """List all tasks with status 'available'."""
        tasks = []
        for path in get_msg_dir(MSG_TYPE_TASK_OFFER).glob("*.toon"):
            msg = MailMessage.from_toon(path)
            if not msg:
                continue
            # Parse body for TITLE
            title = msg.body.split("\n")[0] if msg.body else "untitled"
            if title.startswith("TITLE: "):
                title = title[7:]
            # Determine status from file
            status = self._read_task_status(msg.msg_id)
            if status == TASK_STATUS_AVAILABLE:
                tasks.append({
                    "msg_id": msg.msg_id,
                    "title": title,
                    "body": msg.body,
                    "created_at": msg.created_at,
                    "status": status,
                })
        return tasks

    def claim(self, task_msg_id: str, claimant_sandbox: str, claimant_role: str = "soldier") -> Optional[dict]:
        """Claim a task atomically. Returns task dict or None if already claimed.

        Uses lock file for atomicity. Lock name = task_msg_id.
        """
        lock_name = task_msg_id
        if not acquire_lock(lock_name):
            return None  # Already claimed

        try:
            # Double-check: is task still available?
            current_status = self._read_task_status(task_msg_id)
            if current_status != TASK_STATUS_AVAILABLE:
                return None

            # Read the task message
            path = msg_file_path(task_msg_id, MSG_TYPE_TASK_OFFER)
            if not path.exists():
                return None

            msg = MailMessage.from_toon(path)
            if not msg:
                return None

            # Write a claim message
            claim_body = f"claimed_by: {claimant_sandbox}:{claimant_role}"
            self.xl.send(
                to_sandbox=msg.from_sandbox,
                body=claim_body,
                msg_type=MSG_TYPE_TASK_CLAIM,
                reply_to=task_msg_id,
                from_role=claimant_role,
                from_sandbox=claimant_sandbox,
            )

            # Update status marker (write a .status file beside the task)
            self._write_task_status(task_msg_id, TASK_STATUS_CLAIMED, claimant_sandbox)

            # Parse body for title
            title = msg.body.split("\n")[0] if msg.body else "untitled"
            if title.startswith("TITLE: "):
                title = title[7:]

            return {
                "msg_id": msg.msg_id,
                "title": title,
                "body": msg.body,
                "created_at": msg.created_at,
                "claimed_by": f"{claimant_sandbox}:{claimant_role}",
            }
        finally:
            # Lock stays held for the duration of the task; released on done/fail
            pass  # Lock remains — released by done() or fail()

    def done(self, task_msg_id: str, result: str, claimant_sandbox: str) -> bool:
        """Mark a claimed task as completed."""
        lock_name = task_msg_id

        # Write task_status message
        self.xl.send(
            to_sandbox="*",
            to_role="*",
            body=result,
            msg_type=MSG_TYPE_TASK_STATUS,
            reply_to=task_msg_id,
            from_role="soldier",
            from_sandbox=claimant_sandbox,
        )

        self._write_task_status(task_msg_id, TASK_STATUS_COMPLETED, claimant_sandbox, result=result)
        release_lock(lock_name)
        return True

    def fail(self, task_msg_id: str, reason: str, claimant_sandbox: str) -> bool:
        """Mark a claimed task as failed."""
        self.xl.send(
            to_sandbox="*",
            to_role="*",
            body=f"FAILED: {reason}",
            msg_type=MSG_TYPE_TASK_STATUS,
            reply_to=task_msg_id,
            from_role="soldier",
            from_sandbox=claimant_sandbox,
        )
        self._write_task_status(task_msg_id, TASK_STATUS_FAILED, claimant_sandbox, result=reason)
        release_lock(task_msg_id)
        return True

    # ── Internal status tracking ────────────────────────────

    def _read_task_status(self, task_msg_id: str) -> str:
        """Read task status from companion status file."""
        status_dir = get_msg_dir(MSG_TYPE_TASK_OFFER) / ".status"
        sp = status_dir / f"{task_msg_id}.status"
        if sp.exists():
            return sp.read_text().strip().split("\n")[0] or TASK_STATUS_AVAILABLE
        return TASK_STATUS_AVAILABLE

    def _write_task_status(self, task_msg_id: str, status: str, claimant: str, result: str = "") -> None:
        """Write task status to companion status file."""
        status_dir = get_msg_dir(MSG_TYPE_TASK_OFFER) / ".status"
        status_dir.mkdir(parents=True, exist_ok=True)
        sp = status_dir / f"{task_msg_id}.status"
        lines = [
            f"status: {status}",
            f"claimant: {claimant}",
        ]
        if result:
            lines.append(f"result: {result}")
        lines.append(f"updated_at: {datetime.now(timezone.utc).isoformat()}")
        sp.write_text("\n".join(lines) + "\n")
```

---

### Step 5: Result Pipe (`exchange/pipe.py`)

```python
"""Result passing between pipeline stages."""

from __future__ import annotations

from hero.exchange.message import (
    MailMessage, MSG_TYPE_PIPE_RESULT,
    STATUS_PENDING, STATUS_DELIVERED,
    get_msg_dir,
)
from hero.exchange.core import ExchangeLayer


class ResultPipe:
    """Pipeline result passing — Soldier A output → Soldier B input."""

    def __init__(self, xl: ExchangeLayer):
        self.xl = xl

    def push(
        self,
        to_sandbox: str,
        to_target: str,
        from_task_id: str,
        result_body: str,
        from_sandbox: str = "",
        from_role: str = "soldier",
        ttl_seconds: int = 7200,
    ) -> str:
        """Push the result of from_task_id as input for the next soldier.

        Returns msg_id of the pipe message.
        """
        return self.xl.send(
            to_sandbox=to_sandbox,
            to_role="soldier",
            body=f"## PIPELINE RESULT: {from_task_id}\n\n{result_body}",
            msg_type=MSG_TYPE_PIPE_RESULT,
            ttl_seconds=ttl_seconds,
            correlation_id=from_task_id,
            from_role=from_role,
            from_sandbox=from_sandbox,
        )

    def pull(self, for_sandbox: str, for_role: str = "soldier") -> MailMessage | None:
        """Get the next pipe result addressed to this soldier. Returns one message."""
        pipe_dir = get_msg_dir(MSG_TYPE_PIPE_RESULT)
        if not pipe_dir.exists():
            return None

        for path in sorted(pipe_dir.glob("*.toon")):
            msg = MailMessage.from_toon(path)
            if not msg:
                continue
            if msg.to_sandbox != for_sandbox or msg.to_role != for_role:
                continue
            if msg.status in (STATUS_PENDING, STATUS_DELIVERED):
                # Mark as delivered
                msg.status = STATUS_DELIVERED
                # Re-write via core
                # (In practice, ExchangeLayer.listen would handle this)
                return msg
        return None

    def status(self, task_id: str) -> dict:
        """Check pipeline status for a task ID."""
        pipe_dir = get_msg_dir(MSG_TYPE_PIPE_RESULT)
        results = []
        for path in pipe_dir.glob("*.toon"):
            msg = MailMessage.from_toon(path)
            if msg and msg.correlation_id == task_id:
                results.append({
                    "msg_id": msg.msg_id,
                    "status": msg.status,
                    "to": f"{msg.to_sandbox}:{msg.to_role}",
                })
        return {
            "task_id": task_id,
            "pipe_messages": results,
            "count": len(results),
        }
```

---

### Step 6: Review (`exchange/review.py`)

```python
"""Adversarial review — independent verification of soldier output."""

from __future__ import annotations

from datetime import datetime, timezone

from hero.exchange.message import (
    MailMessage, MSG_TYPE_REVIEW_REQUEST, MSG_TYPE_REVIEW_RESPONSE,
    STATUS_PENDING, STATUS_READ,
    get_msg_dir,
)
from hero.exchange.core import ExchangeLayer

VERDICT_PASS = "pass"
VERDICT_FLAG = "flag"
VERDICT_FAIL = "fail"


class Review:
    """Adversarial review workflow."""

    def __init__(self, xl: ExchangeLayer):
        self.xl = xl

    def request(
        self,
        target_sandbox: str,
        task_id: str,
        review_instructions: str = "",
        timeout_seconds: int = 600,
        from_role: str = "architect",
        from_sandbox: str = "",
    ) -> str:
        """Request an independent review of a completed task."""
        body = (
            f"REVIEW REQUEST: task {task_id}\n"
            f"Review period: {timeout_seconds}s\n\n"
            f"{review_instructions}"
        ) if review_instructions else (
            f"REVIEW REQUEST: task {task_id}\n"
            f"Please independently verify the output of task {task_id}.\n"
            f"Respond with: PASS | FLAG (reason) | FAIL (reason)"
        )
        return self.xl.send(
            to_sandbox=target_sandbox,
            to_role="soldier",
            body=body,
            msg_type=MSG_TYPE_REVIEW_REQUEST,
            ttl_seconds=timeout_seconds + 300,
            correlation_id=task_id,
            from_role=from_role,
            from_sandbox=from_sandbox,
        )

    def respond(
        self,
        review_msg_id: str,
        verdict: str,
        notes: str = "",
        from_role: str = "soldier",
        from_sandbox: str = "",
    ) -> str | None:
        """Respond to a review request. Returns response msg_id or None."""
        if verdict not in (VERDICT_PASS, VERDICT_FLAG, VERDICT_FAIL):
            return None

        # Read original review request
        original = self.xl.get_message(review_msg_id)
        if not original:
            return None

        body = f"VERDICT: {verdict}\n\n{notes}" if notes else f"VERDICT: {verdict}"
        resp_id = self.xl.send(
            to_sandbox=original.from_sandbox,
            to_role=original.from_role,
            body=body,
            msg_type=MSG_TYPE_REVIEW_RESPONSE,
            reply_to=review_msg_id,
            correlation_id=original.correlation_id,
            from_role=from_role,
            from_sandbox=from_sandbox,
        )
        # Mark original as read
        self.xl.mark_read(review_msg_id)
        return resp_id

    def status(self, task_id: str) -> dict:
        """Check review status for a task."""
        review_dir = get_msg_dir(MSG_TYPE_REVIEW_REQUEST)
        resp_dir = get_msg_dir(MSG_TYPE_REVIEW_RESPONSE)

        requests = []
        for p in review_dir.glob("*.toon"):
            m = MailMessage.from_toon(p)
            if m and m.correlation_id == task_id:
                requests.append({
                    "msg_id": m.msg_id,
                    "status": m.status,
                    "from": f"{m.from_sandbox}:{m.from_role}",
                    "to": f"{m.to_sandbox}:{m.to_role}",
                })

        responses = []
        for p in resp_dir.glob("*.toon"):
            m = MailMessage.from_toon(p)
            if m and m.correlation_id == task_id:
                responses.append({
                    "msg_id": m.msg_id,
                    "reply_to": m.reply_to,
                    "status": m.status,
                    "verdict": m.body.split("\n")[0] if m.body else "unknown",
                })

        return {
            "task_id": task_id,
            "requests": requests,
            "responses": responses,
            "pending": any(r["status"] == STATUS_PENDING for r in requests),
        }
```

---

### Step 7: Reliability (`exchange/reliability.py`)

```python
"""Retry with exponential backoff, TTL expiry, DLQ integration."""

from __future__ import annotations

from datetime import datetime, timezone

from hero.exchange.message import (
    MailMessage, STATUS_PENDING, STATUS_EXPIRED, STATUS_FAILED,
    iter_messages,
)
from hero.reliability.dlq import send_to_dlq

RETRY_BACKOFF = {1: 10, 2: 20, 3: 40}


def check_ttl_and_auto_expire() -> int:
    """Check all messages for TTL expiry. Expired → DLQ.

    Returns count of messages expired.
    """
    count = 0
    for path in iter_messages():
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status == STATUS_PENDING and msg.is_expired:
            msg.status = STATUS_EXPIRED
            from hero.exchange.message import get_msg_dir
            subdir = get_msg_dir(msg.msg_type)
            dest = subdir / f"{msg.msg_id}.toon"
            dest.write_text(msg.to_toon())
            count += 1

    return count


def handle_failed_delivery(msg: MailMessage) -> None:
    """Handle a message that can't be delivered after max retries.

    Sends to Dead Letter Queue.
    """
    msg.status = STATUS_FAILED
    from hero.exchange.message import get_msg_dir
    subdir = get_msg_dir(msg.msg_type)
    dest = subdir / f"{msg.msg_id}.toon"
    dest.write_text(msg.to_toon())

    send_to_dlq(
        task_id=msg.msg_id,
        task_data={
            "msg_id": msg.msg_id,
            "type": msg.msg_type,
            "from_sandbox": msg.from_sandbox,
            "to_sandbox": msg.to_sandbox,
            "body": msg.body[:500],
        },
        error=f"Exchange delivery failed after {msg.delivery_attempts} attempts. TTL expired.",
    )


def purge_old(older_than_minutes: int = 60) -> int:
    """Remove messages that are delivered/read/expired and older than threshold.

    Returns count removed.
    """
    import time
    now = time.time()
    cutoff = now - (older_than_minutes * 60)
    purged = 0
    terminal = {STATUS_EXPIRED, STATUS_FAILED}

    for path in iter_messages():
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status in terminal:
            try:
                mtime = path.stat().st_mtime
                if mtime < cutoff:
                    path.unlink()
                    purged += 1
            except OSError:
                pass

    return purged
```

---

### Step 8: CLI Commands (`commands/exchange.py`)

```python
"""hero exchange — Inter-agent message bus commands."""

from __future__ import annotations

import click

from hero.exchange.core import ExchangeLayer
from hero.exchange.task_list import TaskList
from hero.exchange.pipe import ResultPipe
from hero.exchange.review import Review
from hero.exchange.reliability import purge_old


@click.group()
def exchange():
    """Inter-agent message bus — communicate between soldiers."""
    pass


@exchange.command()
@click.argument("target")
@click.argument("message")
@click.option("--type", "msg_type", default="direct",
              type=click.Choice(["direct", "review", "pipe"]))
@click.option("--priority", default="normal",
              type=click.Choice(["low", "normal", "high", "critical"]))
@click.option("--ttl", default=3600, type=int, help="Message TTL in seconds")
@click.option("--reply-to", default=None, help="Reply to a specific message ID")
def send(target: str, message: str, msg_type: str, priority: str,
         ttl: int, reply_to: str | None):
    """Send a message to a target sandbox.

    TARGET: sandbox name (e.g. "freya") or "sandbox:role" (e.g. "sook-pro:architect")
    """
    parts = target.split(":")
    to_sandbox = parts[0]
    to_role = parts[1] if len(parts) > 1 else "soldier"

    xl = ExchangeLayer()
    msg_id = xl.send(
        to_sandbox=to_sandbox,
        to_role=to_role,
        body=message,
        msg_type=msg_type,
        priority=priority,
        ttl_seconds=ttl,
        reply_to=reply_to,
    )
    click.echo(f"  Sent: {msg_id}")


@exchange.command()
@click.argument("message")
@click.option("--role", default=None, help="Filter: only send to this role")
@click.option("--sandbox", default=None, help="Filter: only send to this sandbox")
@click.option("--priority", default="normal",
              type=click.Choice(["low", "normal", "high", "critical"]))
def broadcast(message: str, role: str | None, sandbox: str | None, priority: str):
    """Broadcast a message to all active soldiers."""
    xl = ExchangeLayer()
    msg_id = xl.broadcast(
        body=message,
        role_filter=role,
        sandbox_filter=sandbox,
        priority=priority,
    )
    click.echo(f"  Broadcast sent: {msg_id}")


@exchange.command()
@click.option("--all", "show_all", is_flag=True, help="Show delivered/read too")
@click.option("--from", "from_sandbox", default=None, help="Filter by sender sandbox")
@click.option("--type", "msg_type", default=None, help="Filter by message type")
@click.option("--watch", is_flag=True, help="Continuous polling")
@click.option("--interval", default=5, type=int, help="Poll interval in watch mode")
def listen(show_all: bool, from_sandbox: str | None, msg_type: str | None,
           watch: bool, interval: int):
    """Listen for incoming messages."""
    xl = ExchangeLayer()

    if watch:
        import time
        try:
            while True:
                _print_inbox(xl, show_all, from_sandbox, msg_type)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    else:
        _print_inbox(xl, show_all, from_sandbox, msg_type)


def _print_inbox(xl: ExchangeLayer, show_all: bool, from_filter: str | None, msg_type: str | None):
    messages = xl.listen(include_delivered=show_all, msg_type=msg_type)

    if not messages:
        click.echo("  No new messages.")
        return

    for msg in messages:
        if from_filter and msg.from_sandbox != from_filter:
            continue
        click.echo(f"  [{msg.msg_id[:8]}] {msg.from_sandbox}:{msg.from_role} → {msg.to_sandbox}:{msg.to_role}")
        click.echo(f"      Type: {msg.msg_type} | Priority: {msg.priority} | Status: {msg.status}")
        # Show first 2 lines of body
        body_lines = msg.body.split("\n")[:2]
        for bl in body_lines:
            click.echo(f"      {bl}")
        click.echo()


@exchange.command()
@click.argument("msg_id")
def mark_read(msg_id: str):
    """Acknowledge a message as read."""
    xl = ExchangeLayer()
    if xl.mark_read(msg_id):
        click.echo(f"  Message {msg_id[:12]} marked as read.")
    else:
        click.echo(f"  Message {msg_id[:12]} not found.")


@exchange.command()
@click.argument("msg_id")
@click.argument("message")
def reply(msg_id: str, message: str):
    """Reply to a message (shortcut for send --reply-to)."""
    xl = ExchangeLayer()
    original = xl.get_message(msg_id)
    if not original:
        click.echo(f"  Message {msg_id[:12]} not found.")
        return
    new_id = xl.send(
        to_sandbox=original.from_sandbox,
        to_role=original.from_role,
        body=message,
        reply_to=msg_id,
    )
    click.echo(f"  Replied: {new_id}")


@exchange.command()
def status():
    """Show exchange queue health."""
    xl = ExchangeLayer()

    pending = 0
    delivered = 0
    read_count = 0
    failed = 0
    expired = 0
    by_type: dict[str, int] = {}

    from hero.exchange.message import iter_messages, MailMessage
    for path in iter_messages():
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status == "pending":
            pending += 1
        elif msg.status == "delivered":
            delivered += 1
        elif msg.status == "read":
            read_count += 1
        elif msg.status == "failed":
            failed += 1
        elif msg.status == "expired":
            expired += 1
        by_type[msg.msg_type] = by_type.get(msg.msg_type, 0) + 1

    roster = xl.get_roster()

    click.echo("  Exchange Layer Status")
    click.echo(f"  ─────────────────────")
    click.echo(f"  Messages:")
    click.echo(f"    Pending:   {pending}")
    click.echo(f"    Delivered: {delivered}")
    click.echo(f"    Read:      {read_count}")
    click.echo(f"    Failed:    {failed}")
    click.echo(f"    Expired:   {expired}")
    click.echo(f"  By type:")
    for t, c in sorted(by_type.items()):
        click.echo(f"    {t}: {c}")
    click.echo(f"  ─────────────────────")
    click.echo(f"  Active roster: {len(roster)} soldier(s)")
    for r in roster:
        click.echo(f"    {r.get('sandbox', '?')} — {r.get('role', '?')} ({r.get('soldier_id', '?')[:8]})")
    click.echo(f"  ─────────────────────")


@exchange.command()
def roster():
    """Show active soldier roster."""
    xl = ExchangeLayer()
    roster = xl.get_roster()
    if not roster:
        click.echo("  No active soldiers.")
        return
    click.echo(f"  Active soldiers: {len(roster)}")
    for r in roster:
        click.echo(f"    {r.get('sandbox', '?')} — {r.get('role', '?')} — {r.get('model', '?')}")
        click.echo(f"      spawned: {r.get('spawned_at', '?')}")


@exchange.command()
@click.option("--type", "msg_type", default=None, help="Purge only this message type")
@click.option("--older-than", default=60, type=int, help="Age threshold in minutes")
def purge(msg_type: str | None, older_than: int):
    """Remove old delivered/read/expired messages."""
    from hero.exchange.message import MailMessage, STATUS_READ, STATUS_EXPIRED, STATUS_FAILED
    import time

    now = time.time()
    cutoff = now - (older_than * 60)
    terminal = {"read", "expired", "failed"}

    removed = 0
    for path in iter_messages(msg_type):
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status in terminal:
            try:
                mtime = path.stat().st_mtime
                if mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                pass

    click.echo(f"  Purged {removed} message(s).")


# ── Task list subcommands ─────────────────────────────────────

@exchange.group()
def task():
    """Shared task list operations."""
    pass


@task.command("post")
@click.argument("title")
@click.argument("description")
@click.option("--files", default=None, help="Comma-separated file list")
@click.option("--depends-on", default=None, help="Comma-separated task IDs")
@click.option("--ttl", default=7200, type=int, help="Task TTL in seconds")
def task_post(title: str, description: str, files: str | None,
              depends_on: str | None, ttl: int):
    """Post a task to the shared task list."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    files_list = [f.strip() for f in files.split(",")] if files else None
    depends_list = [d.strip() for d in depends_on.split(",")] if depends_on else None
    task_id = tl.post(title, description, files=files_list, depends_on=depends_list, ttl_seconds=ttl)
    click.echo(f"  Task posted: {task_id}")


@task.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks including claimed/completed")
@click.option("--mine", is_flag=True, help="Show only tasks I claimed")
def task_list(show_all: bool, mine: bool):
    """List available tasks."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    tasks = tl.list_available()
    if not tasks:
        click.echo("  No available tasks.")
        return

    click.echo(f"  Available tasks: {len(tasks)}")
    for t in tasks:
        click.echo(f"    [{t['msg_id'][:8]}] {t['title']}")
        click.echo(f"      Status: {t['status']}")
        # Show TITLE line
        first_line = t['body'].split("\n")[0]
        click.echo(f"      {first_line}")


@task.command("claim")
@click.argument("task_id")
def task_claim(task_id: str):
    """Claim a task from the shared list."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    result = tl.claim(task_id, claimant_sandbox="self", claimant_role="soldier")
    if result:
        click.echo(f"  Claimed: {result['title']}")
    else:
        click.echo(f"  Could not claim {task_id[:12]} — already claimed or not found.")


@task.command("done")
@click.argument("task_id")
@click.argument("result")
def task_done(task_id: str, result: str):
    """Mark a claimed task as completed."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    if tl.done(task_id, result, claimant_sandbox="self"):
        click.echo(f"  Task {task_id[:12]} marked as completed.")


@task.command("fail")
@click.argument("task_id")
@click.argument("reason")
def task_fail(task_id: str, reason: str):
    """Mark a claimed task as failed."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    if tl.fail(task_id, reason, claimant_sandbox="self"):
        click.echo(f"  Task {task_id[:12]} marked as failed.")


# ── Pipe subcommands ──────────────────────────────────────────

@exchange.group()
def pipe():
    """Pipeline result passing."""
    pass


@pipe.command("push")
@click.argument("target")
@click.argument("task_id")
@click.argument("result", default="")
def pipe_push(target: str, task_id: str, result: str):
    """Push result to next pipeline soldier."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    parts = target.split(":")
    to_sandbox = parts[0]
    to_target = parts[1] if len(parts) > 1 else "soldier"
    msg_id = rp.push(to_sandbox, to_target, task_id, result)
    click.echo(f"  Pipe result pushed: {msg_id}")


@pipe.command("pull")
def pipe_pull():
    """Get next pipe result for this soldier."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    msg = rp.pull(for_sandbox="self", for_role="soldier")
    if msg:
        click.echo(f"  [{msg.msg_id[:8]}] Pipeline result from {msg.from_sandbox}")
        click.echo(msg.body[:500])
    else:
        click.echo("  No pipe results waiting.")


@pipe.command("status")
@click.argument("task_id")
def pipe_status(task_id: str):
    """Show pipeline chain status for a task."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    status_info = rp.status(task_id)
    click.echo(f"  Pipeline for task {task_id[:12]}:")
    for pm in status_info["pipe_messages"]:
        click.echo(f"    [{pm['msg_id'][:8]}] → {pm['to']} ({pm['status']})")


# ── Review subcommands ────────────────────────────────────────

@exchange.group()
def review():
    """Adversarial review operations."""
    pass


@review.command("request")
@click.argument("target")
@click.argument("task_id")
@click.option("--timeout", default=600, type=int, help="Review timeout seconds")
def review_request(target: str, task_id: str, timeout: int):
    """Request independent review of a completed task."""
    xl = ExchangeLayer()
    rv = Review(xl)
    parts = target.split(":")
    target_sandbox = parts[0]
    rev_id = rv.request(
        target_sandbox=target_sandbox,
        task_id=task_id,
        timeout_seconds=timeout,
    )
    click.echo(f"  Review requested: {rev_id}")


@review.command("respond")
@click.argument("msg_id")
@click.argument("verdict", type=click.Choice(["pass", "flag", "fail"]))
@click.argument("notes", default="")
def review_respond(msg_id: str, verdict: str, notes: str):
    """Respond to a review request."""
    xl = ExchangeLayer()
    rv = Review(xl)
    resp_id = rv.respond(msg_id, verdict, notes=notes)
    if resp_id:
        click.echo(f"  Review response sent: {resp_id}")
    else:
        click.echo("  Could not respond — review request not found.")


# ── DLQ subcommands ───────────────────────────────────────────

@exchange.group()
def dlq():
    """Dead letter queue operations."""
    pass


@dlq.command("list")
def dlq_list():
    """List dead letter queue entries."""
    from hero.reliability.dlq import list_dlq
    entries = list_dlq()
    if not entries:
        click.echo("  DLQ is empty.")
        return
    click.echo(f"  DLQ entries: {len(entries)}")
    for e in entries:
        click.echo(f"    [{e['task_id'][:12]}] {e.get('sandbox', '?')}: {e.get('error', '')[:80]}")


@dlq.command("retry")
@click.argument("msg_id")
def dlq_retry(msg_id: str):
    """Re-queue a dead letter message."""
    from hero.reliability.dlq import retry_from_dlq
    new_id = retry_from_dlq(msg_id)
    if new_id:
        click.echo(f"  Re-queued: {new_id}")
    else:
        click.echo(f"  Could not retry {msg_id[:12]}.")
```

---

### Step 9: CLI Registration (`cli.py`)

In `src/hero/cli.py`, find the existing `@click.group()` and add:

```python
from hero.commands.exchange import exchange as exchange_group

# ... existing groups ...

hero.add_command(exchange_group)
```

Add after the last `hero.add_command(...)` call.

---

### Step 10: Integration Points

#### A. `deploy.py` — Add `--exchange` flag

```python
@click.option("--exchange/--no-exchange", default=False,
              help="Enable inter-agent communication via Exchange Layer.")
```

After spawning each soldier, register in roster:

```python
if exchange:
    from hero.exchange.core import ExchangeLayer
    xl = ExchangeLayer()
    xl.register_soldier(
        sandbox=sandbox_name,
        soldier_id=soldier_id,
        role=role,
        model=model_full,
    )
```

#### B. `spawner.py` — Register in roster

In `SoldierSpawner.launch()`, at the end (after `record_success` / before `return soldier_id`):

```python
# Register in exchange roster if exchange is enabled
exchange_enabled = os.environ.get("HERO_EXCHANGE_ENABLED", "").strip() in ("1", "true", "True")
if exchange_enabled:
    from hero.exchange.core import ExchangeLayer
    try:
        xl = ExchangeLayer()
        xl.register_soldier(
            sandbox=sandbox_name,
            soldier_id=soldier_id,
            role=role,
            model=model_full if not model_override else model_override[1],
        )
    except Exception:
        logger.warning("Failed to register in exchange roster", sandbox=sandbox_name)
```

#### C. `go.py` — Add `--exchange` flag

```python
@click.option("--exchange/--no-exchange", default=False,
              help="Enable inter-agent communication for this pipeline.")
```

When `--exchange` is set:
1. Create a correlation_id for the pipeline
2. Pass it to all spawned soldiers
3. Optionally auto-create result pipes between sequential tasks

#### D. `context.py` — Inject exchange context

In `build_context()`, when exchange is enabled, add:

```python
if os.environ.get("HERO_EXCHANGE_ENABLED") == "1":
    context_lines.append("exchange:")
    context_lines.append('  enabled: true')
    context_lines.append(f'  roster: "~/.hero/exchange/roster.toon"')
    context_lines.append(f'  listen_pattern: "direct,critical,review"')
```

---

### Step 11: Tests

Create `tests/test_exchange_core.py`:

```python
"""Tests for Exchange Layer core."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hero.exchange.message import MailMessage, EXCHANGE_DIR
from hero.exchange.core import ExchangeLayer


@pytest.fixture
def temp_exchange_dir():
    with tempfile.TemporaryDirectory() as d:
        old = EXCHANGE_DIR
        EXCHANGE_DIR = Path(d)
        try:
            yield Path(d)
        finally:
            EXCHANGE_DIR = old


def test_send_and_listen(temp_exchange_dir):
    xl = ExchangeLayer()
    msg_id = xl.send(
        to_sandbox="freya",
        to_role="soldier",
        body="Hello from A",
        from_role="soldier",
        from_sandbox="sook-pro",
    )
    assert msg_id.startswith("msg_")

    inbox = xl.listen(for_sandbox="freya", for_role="soldier")
    assert len(inbox) == 1
    assert inbox[0].body == "Hello from A"
    assert inbox[0].status == "delivered"  # listen marks as delivered


def test_mark_read(temp_exchange_dir):
    xl = ExchangeLayer()
    msg_id = xl.send(to_sandbox="freya", body="Test", from_sandbox="sook-pro")
    assert xl.mark_read(msg_id)

    msg = xl.get_message(msg_id)
    assert msg is not None
    assert msg.status == "read"


def test_broadcast(temp_exchange_dir):
    xl = ExchangeLayer()
    xl.register_soldier("sook-pro", "a1", role="soldier")
    xl.register_soldier("freya", "b2", role="soldier")

    bcast_id = xl.broadcast(body="Code freeze!", from_sandbox="lead")
    assert bcast_id.startswith("msg_")


def test_roster_registration(temp_exchange_dir):
    xl = ExchangeLayer()
    xl.register_soldier("sook-pro", "abc123", role="soldier", model="step-3.5-flash")
    roster = xl.get_roster()
    assert len(roster) == 1
    assert roster[0]["sandbox"] == "sook-pro"

    xl.unregister_soldier("abc123")
    assert len(xl.get_roster()) == 0
```

Create `tests/test_exchange_task_list.py`, `tests/test_exchange_pipe.py`, `tests/test_exchange_review.py`, `tests/test_exchange_reliability.py` following the same pattern.

---

## Implementation Order

```
Phase 1: Foundation
  Step 1: message.py (data model + TOON serialization)
  Step 2: lock.py (atomic file locks)
  Step 3: core.py (ExchangeLayer: send/listen/roster)
  Step 8: commands/exchange.py (CLI: send/listen/status/roster)
  Step 9: cli.py (register exchange command group)

Phase 2: Patterns
  Step 4: task_list.py (shared task list with atomic claim)
  Step 5: pipe.py (result passing)
  Step 6: review.py (adversarial review)

Phase 3: Reliability
  Step 7: reliability.py (TTL expiry, purge, DLQ)
  Add dlq list/retry to CLI

Phase 4: Integration
  Step 10: deploy.py, spawner.py, go.py, context.py
  Wire up --exchange flags

Phase 5: Tests
  Step 11: Write unit tests for all modules
```

---

## Acceptance Criteria

1. `hero exchange send freya "hello"` creates a `.toon` file in `~/.hero/exchange/direct/`
2. `hero exchange listen` (from freya context) returns the message
3. `hero exchange broadcast "hi"` creates a message in `~/.hero/exchange/broadcast/`
4. `hero exchange status` shows correct counts
5. `hero exchange task post` creates task; `claim`, `done` work with atomic locking
6. `hero exchange pipe push/pull` passes result between stages
7. `hero exchange review request/respond` enables adversarial review
8. `hero deploy --targets X,Y --exchange` registers soldiers in roster
9. No existing functionality breaks when `--exchange` flag is absent
10. Old messages auto-expire and get purged or sent to DLQ
11. Concurrent claims on same task: only one succeeds (lock file test)
12. All new modules have >80% test coverage
