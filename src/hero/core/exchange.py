"""Exchange — inter-soldier communication.

Messages are stored as
``~/.hero/exchange/channels/<channel>/messages/<soldier_id>-<seq>.json``.
Contention is eliminated because filenames are unique per soldier per
write — no locking required for message posts.

Shared channel state (``state.json``) **does** use a ``FileLock`` from
``hero.core.locks`` to serialise concurrent writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXCHANGE_DIR = Path.home() / ".hero" / "exchange"
CHANNEL_DIR = EXCHANGE_DIR / "channels"


def ensure_channel(channel: str) -> Path:
    """Create (if needed) and return the messages directory for *channel*.

    Args:
        channel: Channel name (arbitrary string).

    Returns:
        ``Path`` to the ``messages/`` sub-directory for the channel.
    """
    path = CHANNEL_DIR / channel / "messages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def post_message(channel: str, soldier_id: str, message: dict[str, Any]) -> Path:
    """Post a message from *soldier_id* into *channel*.

    Messages are written as zero-contention per-soldier sequenced JSON
    files.  No lock is needed because each soldier writes to a unique
    filename.

    Args:
        channel:    Channel name.
        soldier_id: Identifier of the posting soldier (e.g. task ID).
        message:    Arbitrary JSON-serialisable dict.

    Returns:
        Path to the file that was written.
    """
    msg_dir = ensure_channel(channel)
    seq = len(list(msg_dir.glob(f"{soldier_id}-*.json"))) + 1
    msg_path = msg_dir / f"{soldier_id}-{seq:04d}.json"
    msg_path.write_text(json.dumps(message, indent=2, default=str))
    return msg_path


def read_messages(channel: str) -> list[dict[str, Any]]:
    """Read all messages from *channel* in filename order.

    Args:
        channel: Channel name.

    Returns:
        List of message dicts (empty if channel does not exist or has no
        messages).
    """
    msg_dir = CHANNEL_DIR / channel / "messages"
    if not msg_dir.exists():
        return []
    messages: list[dict[str, Any]] = []
    for f in sorted(msg_dir.glob("*.json")):
        messages.append(json.loads(f.read_text()))
    return messages


def read_state(channel: str) -> dict[str, Any] | None:
    """Read the shared channel state.

    Args:
        channel: Channel name.

    Returns:
        The state dict, or ``None`` if no state file exists.
    """
    state_path = CHANNEL_DIR / channel / "state.json"
    if state_path.exists():
        return json.loads(state_path.read_text())
    return None


def write_state(channel: str, state: dict[str, Any]) -> None:
    """Write shared channel state under a ``FileLock``.

    Uses ``hero.core.locks.FileLock`` with resource name
    ``exchange_state_<channel>`` to serialise concurrent state writes.

    Args:
        channel: Channel name.
        state:   JSON-serialisable state dict to persist.
    """
    from hero.core.locks import FileLock

    with FileLock(f"exchange_state_{channel}"):
        state_path = CHANNEL_DIR / channel / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, default=str))
