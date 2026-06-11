"""Shared task list with atomic claim locking + per-soldier assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hero.exchange.message import (
    MailMessage,
    EXCHANGE_DIR,
    MSG_TYPE_TASK_OFFER,
    MSG_TYPE_TASK_CLAIM,
    MSG_TYPE_TASK_STATUS,
    TASK_STATUS_AVAILABLE,
    TASK_STATUS_CLAIMED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    get_msg_dir,
    msg_file_path,
    STATUS_PENDING,
)
from hero.exchange.lock import acquire_lock, release_lock
from hero.exchange.core import ExchangeLayer
from hero.logging import get_logger

logger = get_logger("exchange.task_list")


class Assignment:
    """Per-soldier assignment file.

    Guardrail 4: soldier reads ONE file, not the full task list, to find its work.
    """

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
            lines = [f'deploy_id: "{deploy_id}"']
            for k, v in data.items():
                if isinstance(v, str):
                    lines.append(f'{k}: "{v}"')
                else:
                    lines.append(f"{k}: {v}")
            path.write_text("\n".join(lines) + "\n")
        logger.info("Assignments written", deploy_id=deploy_id, count=len(assignments))

    @staticmethod
    def read_assignment(deploy_id: str, soldier_id: str) -> dict | None:
        """Read this soldier's assignment file. Returns dict or None."""
        from hero.soldier.dispatch import _parse_toon_file

        path = EXCHANGE_DIR / deploy_id / "assignments" / f"{soldier_id}.toon"
        if not path.exists():
            return None
        return _parse_toon_file(path.read_text())

    @staticmethod
    def remove_assignments(deploy_id: str) -> None:
        """Clean up assignments when exchange is done."""
        assign_dir = EXCHANGE_DIR / deploy_id / "assignments"
        if assign_dir.exists():
            import shutil

            shutil.rmtree(assign_dir)
            logger.debug("Assignments cleaned up", deploy_id=deploy_id)


class TaskList:
    """Shared task list for Lead → Workers pattern.

    Guardrail: Soldiers use Assignment file to find their task,
    not scanning the full TASKS.toon.
    """

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

        return self.xl.send(
            to_sandbox="*",
            to_role="*",
            body=body,
            msg_type=MSG_TYPE_TASK_OFFER,
            ttl_seconds=ttl_seconds,
            from_role=from_role,
            from_sandbox=from_sandbox,
            from_model=from_model,
        )

    def list_available(self) -> list[dict]:
        """List all tasks with status 'available'."""
        tasks: list[dict] = []
        for path in get_msg_dir(MSG_TYPE_TASK_OFFER).glob("*.toon"):
            msg = MailMessage.from_toon(path)
            if not msg:
                continue
            title = msg.body.split("\n")[0] if msg.body else "untitled"
            if title.startswith("TITLE: "):
                title = title[7:]
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
        Guardrail: first-claim-wins (lock file prevents race).
        """
        if not acquire_lock(task_msg_id):
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

            # Update status marker
            self._write_task_status(task_msg_id, TASK_STATUS_CLAIMED, claimant_sandbox)

            title = msg.body.split("\n")[0] if msg.body else "untitled"
            if title.startswith("TITLE: "):
                title = title[7:]

            logger.info("Task claimed", task_id=task_msg_id[:12], claimant=claimant_sandbox)
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
        release_lock(task_msg_id)
        logger.info("Task completed", task_id=task_msg_id[:12], claimant=claimant_sandbox)
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
        logger.warning("Task failed", task_id=task_msg_id[:12], claimant=claimant_sandbox, reason=reason)
        return True

    # ── Internal status tracking ────────────────────────────

    def _read_task_status(self, task_msg_id: str) -> str:
        """Read task status from companion status file."""
        status_dir = get_msg_dir(MSG_TYPE_TASK_OFFER) / ".status"
        sp = status_dir / f"{task_msg_id}.status"
        if sp.exists():
            content = sp.read_text().strip()
            first_line = content.split("\n")[0]
            if first_line.startswith("status: "):
                return first_line[8:]
            return content
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
