"""Advisory file locking for HERO shared state.

Provides a ``FileLock`` context manager that uses ``fcntl.flock`` for
process-level exclusive access to shared resources like pipeline manifests
and sandbox indices.
"""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path

LOCK_DIR = Path.home() / ".hero" / "locks"


class FileLock:
    """Advisory file lock via ``fcntl.flock``. Use as a context manager.

    Acquires an exclusive non-blocking lock, retrying on ``IOError`` /
    ``OSError`` until the *timeout* window expires.  Raise
    ``TimeoutError`` if the lock cannot be acquired in time.

    Usage::

        with FileLock("pipeline_manifest"):
            manifest_path.write_text(json.dumps(data))

    The lock file is created under ``~/.hero/locks/<resource_name>.lock``.
    """

    def __init__(
        self,
        resource_name: str,
        timeout: float = 30.0,
        poll: float = 0.1,
    ) -> None:
        """Initialise a lock for *resource_name*.

        Args:
            resource_name: Unique name for the shared resource.
            timeout:        Max seconds to wait for the lock (default 30).
            poll:           Sleep interval between acquisition attempts
                            (default 0.1 s).
        """
        self.lock_path = LOCK_DIR / f"{resource_name}.lock"
        self.timeout = timeout
        self.poll = poll
        self.fd: int | None = None

    def __enter__(self) -> FileLock:
        """Acquire the exclusive lock, blocking until acquired or timed out.

        Returns:
            The ``FileLock`` instance for use as a context manager.

        Raises:
            TimeoutError: If the lock cannot be acquired within *timeout*.
        """
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (IOError, OSError):
                time.sleep(self.poll)
        raise TimeoutError(
            f"Could not acquire lock on {self.lock_path.name} "
            f"within {self.timeout}s"
        )

    def __exit__(self, *args: object) -> None:
        """Release the lock and close the file descriptor."""
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
