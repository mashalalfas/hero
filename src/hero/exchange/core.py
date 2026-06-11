"""Core ExchangeLayer class — send, listen, mark_read, roster."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hero.exchange.message import (
    MailMessage,
    EXCHANGE_DIR,
    MSG_DIR_MAP,
    MSG_TYPE_DIRECT,
    MSG_TYPE_BROADCAST,
    STATUS_PENDING,
    STATUS_DELIVERED,
    STATUS_READ,
    STATUS_FAILED,
    PRIORITY_NORMAL,
    ALL_PRIORITIES,
    get_msg_dir,
    msg_file_path,
    iter_messages,
)
from hero.exchange.reliability import check_ttl_and_auto_expire
from hero.logging import get_logger
from hero.state.status import write_status

logger = get_logger("exchange.core")

EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)

# Roster
ROSTER_PATH = EXCHANGE_DIR / "roster.toon"
ARCHIVE_DIR = EXCHANGE_DIR / "messages" / "archive"

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


class ExchangeLayer:
    """Primary API for the Exchange Layer message bus.

    Guardrail: Lead is NOT in the message path. Messages go soldier → .toon → soldier.
    Guardrail: listen() caps at max_results=5 to prevent context flooding.
    Guardrail: mark_read() archives messages so soldiers never re-read stale data.
    """

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
        """Send a message. Returns msg_id.

        Guardrail: Each message has exactly ONE recipient. No implicit CC to Lead.
        """
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
        logger.debug(
            "Message sent",
            msg_id=msg.msg_id,
            msg_type=msg.msg_type,
            to_sandbox=to_sandbox,
            from_sandbox=from_sandbox,
        )
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
        # Write a single broadcast message; soldiers find it via listen()
        # by checking their sandbox/role against the roster and the broadcast
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
        logger.debug("Broadcast sent", msg_id=msg.msg_id)
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

        Guardrail: max_results=5 prevents context flooding.
        Guardrail: priority_min filters out low-priority noise.

        Returns pending messages by default, capped at max_results.
        If include_delivered=True, also returns delivered-not-read messages.
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
        priority_min_order = PRIORITY_ORDER.get(priority_min, 2)
        messages = [m for m in messages if PRIORITY_ORDER.get(m.priority, 2) <= priority_min_order]
        messages.sort(key=lambda m: (PRIORITY_ORDER.get(m.priority, 2), m.created_at))

        # Guardrail 3: cap at max_results
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
                    if archive_path:
                        logger.debug("Message archived", msg_id=msg_id)
                        return True
        return False

    def get_message(self, msg_id: str) -> MailMessage | None:
        """Retrieve a specific message by ID."""
        for path in iter_messages():
            if path.stem == msg_id:
                return MailMessage.from_toon(path)
        # Also check archive
        archive_dir = EXCHANGE_DIR / "messages" / "archive"
        if archive_dir.exists():
            for path in sorted(archive_dir.glob("*.toon")):
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
        logger.info("Soldier registered", sandbox=sandbox, soldier_id=soldier_id[:8], role=role)

    def unregister_soldier(self, soldier_id: str) -> None:
        """Remove a soldier from the active roster."""
        roster = self._load_roster()
        roster = [e for e in roster if e.get("soldier_id") != soldier_id]
        self._save_roster(roster)
        logger.info("Soldier unregistered", soldier_id=soldier_id[:8])

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
                path.rename(dest)
                return dest
        return None

    def _load_roster(self) -> list[dict]:
        """Load roster from disk (JSON format)."""
        if not ROSTER_PATH.exists():
            return []
        import json
        try:
            data = json.loads(ROSTER_PATH.read_text())
            return data.get("entries", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _save_roster(self, entries: list[dict]) -> None:
        """Save roster to disk as JSON (TOON parser doesn't support nested lists)."""
        import json
        ROSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "count": len(entries),
            "entries": entries,
        }
        ROSTER_PATH.write_text(json.dumps(data, indent=2))
