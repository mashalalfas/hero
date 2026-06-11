"""Result passing between pipeline stages."""

from __future__ import annotations

from hero.exchange.message import (
    MailMessage,
    MSG_TYPE_PIPE_RESULT,
    STATUS_PENDING,
    STATUS_DELIVERED,
    get_msg_dir,
)
from hero.exchange.core import ExchangeLayer
from hero.logging import get_logger

logger = get_logger("exchange.pipe")


class ResultPipe:
    """Pipeline result passing — Soldier A output → Soldier B input.

    Guardrail: Lead is NOT in the path. Results flow soldier → .toon → next soldier.
    """

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
        msg_id = self.xl.send(
            to_sandbox=to_sandbox,
            to_role=to_target,
            body=f"## PIPELINE RESULT: {from_task_id}\n\n{result_body}",
            msg_type=MSG_TYPE_PIPE_RESULT,
            ttl_seconds=ttl_seconds,
            correlation_id=from_task_id,
            from_role=from_role,
            from_sandbox=from_sandbox,
        )
        logger.debug(
            "Pipe result pushed",
            to_sandbox=to_sandbox,
            task_id=from_task_id,
            msg_id=msg_id,
        )
        return msg_id

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
                return msg
        return None

    def status(self, task_id: str) -> dict:
        """Check pipeline status for a task ID."""
        pipe_dir = get_msg_dir(MSG_TYPE_PIPE_RESULT)
        results: list[dict] = []
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
