"""MailMessage dataclass + TOON serialization for Exchange Layer."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hero.logging import get_logger

logger = get_logger("exchange.message")

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

# Message type → subdirectory mapping
MSG_DIR_MAP: dict[str, str] = {
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
    """Return the subdirectory for a given message type under EXCHANGE_DIR."""
    sub = MSG_DIR_MAP.get(msg_type, "direct")
    return EXCHANGE_DIR / sub


def msg_file_path(msg_id: str, msg_type: str) -> Path:
    """Return the full path for a message file."""
    return get_msg_dir(msg_type) / f"{msg_id}.toon"


def iter_messages(msg_type: str | None = None) -> list[Path]:
    """Iterate all message files, optionally filtered by type.

    Excludes archive/ directory.
    """
    if msg_type:
        subs = [MSG_DIR_MAP.get(msg_type, "direct")]
    else:
        subs = set(MSG_DIR_MAP.values())
    files: list[Path] = []
    for sub in subs:
        d = EXCHANGE_DIR / sub
        if d.exists():
            for f in sorted(d.glob("*.toon")):
                # Skip archive files
                if "archive" in f.parts:
                    continue
                files.append(f)
    return files


@dataclass
class MailMessage:
    """A single exchange message stored as a .toon file."""

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

    def __post_init__(self) -> None:
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
        try:
            from hero.soldier.dispatch import _parse_toon_file
            data = _parse_toon_file(path.read_text())
            if not data:
                return None
            # Only pass fields that exist on the dataclass
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            return cls(**filtered)
        except Exception as exc:
            logger.warning("Failed to parse message", path=str(path), error=str(exc))
            return None

    def to_toon(self) -> str:
        """Serialize to TOON format string."""
        lines: list[str] = []
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
