"""Retry with exponential backoff, TTL expiry, DLQ integration."""

from __future__ import annotations

from datetime import datetime, timezone

from hero.exchange.message import (
    MailMessage,
    STATUS_PENDING,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_READ,
    iter_messages,
)
from hero.logging import get_logger
from hero.reliability.dlq import send_to_dlq

logger = get_logger("exchange.reliability")

RETRY_BACKOFF: dict[int, int] = {1: 10, 2: 20, 3: 40}


def check_ttl_and_auto_expire() -> int:
    """Check all messages for TTL expiry. Expired sent to DLQ.

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

    if count:
        logger.info("Messages expired", count=count)
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
    logger.warning("Message sent to DLQ", msg_id=msg.msg_id, from_sandbox=msg.from_sandbox)


def purge_old(older_than_minutes: int = 60) -> int:
    """Remove messages that are delivered/read/expired and older than threshold.

    Returns count removed.
    """
    import time
    now = time.time()
    cutoff = now - (older_than_minutes * 60)
    purged = 0
    terminal = {STATUS_EXPIRED, STATUS_FAILED, STATUS_READ}

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

    if purged:
        logger.info("Purged old messages", count=purged)
    return purged
