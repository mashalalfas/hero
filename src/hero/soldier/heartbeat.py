"""Katana checkpoint management for soldier heartbeats."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hero.state.toon import toon_read, toon_write


class KatanaCheckpoint:
    """Manages TOON checkpoint files for soldier state."""

    def __init__(self, sandbox_path: Path):
        """Initialize checkpoint manager for a sandbox.

        Args:
            sandbox_path: Path to the sandbox directory.
        """
        self.sandbox_path = sandbox_path
        self.memory_path = sandbox_path / "MEMORY.toon"

    def update(
        self,
        sandbox: str,
        pending: list[str],
        known_issues: list[str],
    ) -> None:
        """Update the sandbox checkpoint with pending tasks and known issues.

        Loads existing MEMORY.toon, updates the katana section, and saves back.

        Args:
            sandbox: Sandbox name.
            pending: List of pending tasks.
            known_issues: List of known issues.
        """
        data = {}
        if self.memory_path.exists():
            data = toon_read(self.memory_path)

        timestamp = datetime.now().isoformat()

        data["katana"] = {
            "pending": pending,
            "known_issues": known_issues,
            "checkpointed_at": timestamp,
        }

        lines = ["{"]
        lines.append(f"  sandbox: {sandbox}")
        lines.append("  katana{")
        lines.append(f"    pending[{len(pending)}]: {', '.join(pending) if pending else 'none'}")
        lines.append(f"    known_issues[{len(known_issues)}]: {', '.join(known_issues) if known_issues else 'none'}")
        lines.append(f"    checkpointed_at: {timestamp}")
        lines.append("  }")
        lines.append("}")

        self.memory_path.write_text("\n".join(lines) + "\n")


"""Soldier heartbeat monitoring system.

Monitors soldier health via HEARTBEAT.toon files in sandbox directories.
When a soldier spawns, a heartbeat file is created with soldier_id, timestamps,
and status. Soldiers ping periodically to show they're alive. Missing 3+ pings
marks a soldier as "stale".
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hero.state.toon import toon_read, toon_write


# Threshold for marking a soldier as stale (missed consecutive pings)
STALE_THRESHOLD = 3


@dataclass
class HeartbeatData:
    """Heartbeat state for a soldier."""
    soldier_id: str
    sandbox_name: str
    started_at: str
    last_ping: str
    missed_count: int = 0
    status: str = "active"  # active, stale, completed


class HeartbeatState:
    """Manages soldier heartbeat files.

    Heartbeat files are stored at ~/.hero/sandboxes/<name>/HEARTBEAT.toon
    and track:
    - soldier_id: unique ID for the soldier
    - started_at: ISO timestamp when soldier started
    - last_ping: ISO timestamp of last heartbeat ping
    - missed_count: consecutive missed pings (resets on ping)
    - status: active | stale | completed

    If missed_count >= 3, status is marked "stale".
    """

    def __init__(self, sandbox_name: str, base_path: Path | None = None) -> None:
        """Initialize HeartbeatState for a sandbox.

        Args:
            sandbox_name: Name of the sandbox.
            base_path: Optional base path (defaults to ~/.hero/sandboxes).
        """
        self.sandbox_name = sandbox_name
        if base_path:
            self.base_path = base_path / sandbox_name
        else:
            from hero.state.sandbox import SANDBOX_DIR
            self.base_path = SANDBOX_DIR / sandbox_name

    @property
    def heartbeat_file(self) -> Path:
        """Return path to the heartbeat file."""
        return self.base_path / "HEARTBEAT.toon"

    def create(self, soldier_id: str) -> HeartbeatData:
        """Create a new heartbeat file when a soldier spawns.

        Args:
            soldier_id: Unique ID for the spawned soldier.

        Returns:
            HeartbeatData for the created heartbeat.
        """
        now = datetime.now().isoformat()
        data = HeartbeatData(
            soldier_id=soldier_id,
            sandbox_name=self.sandbox_name,
            started_at=now,
            last_ping=now,
            missed_count=0,
            status="active",
        )
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._write(data)
        return data

    def ping(self, soldier_id: str) -> HeartbeatData | None:
        """Update last_ping timestamp and reset missed count.

        Args:
            soldier_id: ID of the soldier sending the ping.

        Returns:
            Updated HeartbeatData or None if no heartbeat exists.
        """
        heartbeat = self._read()
        if heartbeat is None:
            return None

        # Verify soldier_id matches
        if heartbeat.soldier_id != soldier_id:
            return None

        heartbeat.last_ping = datetime.now().isoformat()
        heartbeat.missed_count = 0
        heartbeat.status = "active"
        self._write(heartbeat)
        return heartbeat

    def miss(self) -> HeartbeatData | None:
        """Increment missed_count and mark stale if threshold reached.

        Returns:
            Updated HeartbeatData or None if no heartbeat exists.
        """
        heartbeat = self._read()
        if heartbeat is None:
            return None

        heartbeat.missed_count += 1
        if heartbeat.missed_count >= STALE_THRESHOLD:
            heartbeat.status = "stale"
        self._write(heartbeat)
        return heartbeat

    def complete(self) -> HeartbeatData | None:
        """Mark the soldier as completed.

        Returns:
            Updated HeartbeatData or None if no heartbeat exists.
        """
        heartbeat = self._read()
        if heartbeat is None:
            return None

        heartbeat.status = "completed"
        heartbeat.last_ping = datetime.now().isoformat()
        self._write(heartbeat)
        return heartbeat

    def get_heartbeat(self) -> HeartbeatData | None:
        """Get current heartbeat data.

        Returns:
            HeartbeatData or None if no heartbeat file exists.
        """
        return self._read()

    def is_stale(self) -> bool:
        """Check if the soldier is marked as stale.

        Returns:
            True if status is "stale", False otherwise.
        """
        heartbeat = self._read()
        return heartbeat is not None and heartbeat.status == "stale"

    @staticmethod
    def get_stale_sandboxes(base_path: Path | None = None) -> list[str]:
        """Find all sandboxes with stale soldiers.

        Args:
            base_path: Optional base path (defaults to ~/.hero/sandboxes).

        Returns:
            List of sandbox names with stale soldiers.
        """
        from hero.state.sandbox import SANDBOX_DIR

        sandboxes_dir = base_path if base_path else SANDBOX_DIR
        if not sandboxes_dir.exists():
            return []

        stale = []
        for sandbox_path in sandboxes_dir.iterdir():
            if not sandbox_path.is_dir():
                continue
            heartbeat_file = sandbox_path / "HEARTBEAT.toon"
            if not heartbeat_file.exists():
                continue
            data = toon_read(heartbeat_file)
            if data.get("status") == "stale":
                stale.append(sandbox_path.name)
        return stale

    @staticmethod
    def get_all_heartbeats(base_path: Path | None = None) -> dict[str, HeartbeatData]:
        """Get heartbeat data for all sandboxes.

        Args:
            base_path: Optional base path (defaults to ~/.hero/sandboxes).

        Returns:
            Dict mapping sandbox name to HeartbeatData.
        """
        from hero.state.sandbox import SANDBOX_DIR

        sandboxes_dir = base_path if base_path else SANDBOX_DIR
        result = {}

        if not sandboxes_dir.exists():
            return result

        for sandbox_path in sandboxes_dir.iterdir():
            if not sandbox_path.is_dir():
                continue
            heartbeat_file = sandbox_path / "HEARTBEAT.toon"
            if not heartbeat_file.exists():
                continue
            data = toon_read(heartbeat_file)
            if data.get("soldier_id"):
                result[sandbox_path.name] = HeartbeatData(
                    soldier_id=data.get("soldier_id", ""),
                    sandbox_name=sandbox_path.name,
                    started_at=data.get("started_at", ""),
                    last_ping=data.get("last_ping", ""),
                    missed_count=data.get("missed_count", 0),
                    status=data.get("status", "unknown"),
                )
        return result

    def _read(self) -> HeartbeatData | None:
        """Read heartbeat data from file."""
        if not self.heartbeat_file.exists():
            return None
        data = toon_read(self.heartbeat_file)
        if not data.get("soldier_id"):
            return None
        return HeartbeatData(
            soldier_id=data.get("soldier_id", ""),
            sandbox_name=data.get("name", self.sandbox_name),
            started_at=data.get("started_at", ""),
            last_ping=data.get("last_ping", ""),
            missed_count=data.get("missed_count", 0),
            status=data.get("status", "unknown"),
        )

    def _write(self, heartbeat: HeartbeatData) -> None:
        """Write heartbeat data to file."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        toon_write(self.heartbeat_file, {
            "soldier_id": heartbeat.soldier_id,
            "name": heartbeat.sandbox_name,
            "started_at": heartbeat.started_at,
            "last_ping": heartbeat.last_ping,
            "missed_count": heartbeat.missed_count,
            "status": heartbeat.status,
        })