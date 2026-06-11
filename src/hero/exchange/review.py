"""Adversarial review — independent verification of soldier output."""

from __future__ import annotations

from hero.exchange.message import (
    MailMessage,
    MSG_TYPE_REVIEW_REQUEST,
    MSG_TYPE_REVIEW_RESPONSE,
    STATUS_PENDING,
    STATUS_READ,
    get_msg_dir,
)
from hero.exchange.core import ExchangeLayer
from hero.logging import get_logger

logger = get_logger("exchange.review")

VERDICT_PASS = "pass"
VERDICT_FLAG = "flag"
VERDICT_FAIL = "fail"


class Review:
    """Adversarial review workflow.

    Guardrail: Reviewer reads work independently, writes verdict.
    No 'CC the Lead' — Lead reads the verdict file if it wants to know.
    """

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
        msg_id = self.xl.send(
            to_sandbox=target_sandbox,
            to_role="soldier",
            body=body,
            msg_type=MSG_TYPE_REVIEW_REQUEST,
            ttl_seconds=timeout_seconds + 300,
            correlation_id=task_id,
            from_role=from_role,
            from_sandbox=from_sandbox,
        )
        logger.info("Review requested", task_id=task_id, target=target_sandbox, msg_id=msg_id[:8])
        return msg_id

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
            logger.warning("Invalid verdict", verdict=verdict)
            return None

        # Read original review request
        original = self.xl.get_message(review_msg_id)
        if not original:
            logger.warning("Review request not found", msg_id=review_msg_id)
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
        # Mark original as read (archives it, Guardrail 5)
        self.xl.mark_read(review_msg_id)
        logger.info("Review responded", msg_id=review_msg_id, verdict=verdict)
        return resp_id

    def status(self, task_id: str) -> dict:
        """Check review status for a task."""
        review_dir = get_msg_dir(MSG_TYPE_REVIEW_REQUEST)
        resp_dir = get_msg_dir(MSG_TYPE_REVIEW_RESPONSE)

        requests: list[dict] = []
        for p in review_dir.glob("*.toon"):
            m = MailMessage.from_toon(p)
            if m and m.correlation_id == task_id:
                requests.append({
                    "msg_id": m.msg_id,
                    "status": m.status,
                    "from": f"{m.from_sandbox}:{m.from_role}",
                    "to": f"{m.to_sandbox}:{m.to_role}",
                })

        responses: list[dict] = []
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
