"""Pipeline Watcher — background daemon that monitors dispatch files
and automatically updates pipeline manifest state when soldiers complete.

The core gap: when ``sessions_spawn`` subagents finish, OpenClaw sends
completion events back as messages — but nobody calls ``mark_completed()``
on the dispatch file.  The dispatch file stays at ``"dispatched"`` forever
and the pipeline manifest never advances.

The watcher bridges this gap by:

1. Polling dispatch files for stale ``"dispatched"`` entries
2. Checking whether the associated OpenClaw session is still alive
3. If the session ended (or the file was externally updated), syncing
   the pipeline manifest so the viewport shows live progress

Usage::

    from hero.pipeline.watcher import PipelineWatcher

    watcher = PipelineWatcher()
    watcher.run()           # blocking loop
    # or
    watcher.start()         # background thread
    watcher.stop()          # graceful shutdown
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.logging import get_logger
from hero.soldier.dispatch import (
    DISPATCH_DIR,
    get_task,
    list_all,
    mark_completed,
    mark_failed,
)
from hero.state.usage import get_usage, sum_sandbox_usage
from hero.state.budget import BudgetState

PIPELINE_DIR = Path.home() / ".hero" / "pipeline"
DLQ_DIR = Path.home() / ".hero" / "dlq"

# How often (seconds) the watcher scans for completed tasks.
WATCH_INTERVAL = 3

# Grace period (seconds) after dispatch before we start checking session status.
# This prevents false negatives while the subagent is still booting.
DISPATCH_GRACE_PERIOD = 15

# How stale (seconds) a "dispatched" entry must be before we actively probe it.
STALENESS_THRESHOLD = 20

logger = get_logger("watcher")


class PipelineWatcher:
    """Monitors dispatch files and updates pipeline state when soldiers complete.

    The watcher runs a simple poll loop:

    1. Read all dispatch files
    2. For each ``"dispatched"`` task older than the grace period, check
       if its OpenClaw session is still alive
    3. If the session is gone → mark completed (or failed) and sync
       the pipeline manifest
    4. For tasks already ``"completed"`` / ``"failed"`` but not yet
       reflected in the pipeline manifest, sync them

    Thread-safe: can be started as a daemon thread via :meth:`start`.
    """

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._synced_tasks: set[str] = set()  # task_ids already synced to manifest
        self._session_cache: dict[str, bool] = {}
        self._cache_ttl: dict[str, float] = {}
        self._last_cleanup_ts: float = 0.0
        self._stale_sweep_interval: float = 3600  # 1 hour between full stale sweeps

    # ── Lifecycle ──────────────────────────────────────────────────────

    def run(self) -> None:
        """Main loop — blocks until :meth:`stop` is called."""
        self._running = True
        logger.info("Pipeline Watcher started", interval=WATCH_INTERVAL)
        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("Watcher tick failed")
            time.sleep(WATCH_INTERVAL)
        logger.info("Pipeline Watcher stopped")

    def start(self) -> None:
        """Start the watcher as a daemon thread (non-blocking)."""
        if self._thread and self._thread.is_alive():
            logger.warning("Watcher already running")
            return
        self._thread = threading.Thread(target=self.run, daemon=True, name="hero-watcher")
        self._thread.start()
        logger.info("Watcher thread started")

    def stop(self) -> None:
        """Signal the watcher to stop.  Non-blocking."""
        self._running = False
        logger.info("Watcher stop requested")

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ── Core tick ──────────────────────────────────────────────────────

    def _tick(self) -> None:
        """One scan cycle: check dispatch files, sync pipeline state, clean up completed."""
        tasks = list_all()
        now = time.time()

        # After each tick, run pipeline cleanup (archive completed manifests)
        self._cleanup_completed_pipelines(now)

        for task in tasks:
            tid = task.get("task_id", "")
            status = task.get("status", "")

            # ── Case 1: Task already terminal — just sync to manifest ──
            if status in ("completed", "failed"):
                if tid not in self._synced_tasks:
                    sandbox = task.get("sandbox", "")
                    result = task.get("result", "")
                    self._sync_pipeline_manifest(sandbox, tid, status, result)
                    self._synced_tasks.add(tid)
                    if status == "completed":
                        logger.info(
                            "Synced completed task to pipeline",
                            task_id=tid,
                            sandbox=sandbox,
                        )
                        # Track budget for completed tasks
                        self._track_budget(sandbox, tid, status)
                    else:
                        logger.info(
                            "Synced failed task to pipeline",
                            task_id=tid,
                            sandbox=sandbox,
                        )
                        # Track budget for failed tasks (estimate usage)
                        self._track_budget(sandbox, tid, status)
                continue

            # ── Case 2: Task is "dispatched" — check if session ended ──
            if status == "dispatched":
                # Only auto-complete metadata tasks (archive, verify, etc.).
                # Soldier tasks must be marked completed only by the Communicator
                # to avoid false positives from stale git-status checks.
                role = task.get("role", "soldier")
                if role == "soldier":
                    continue

                dispatched_at = task.get("dispatched_at")
                if dispatched_at:
                    try:
                        dt = datetime.fromisoformat(dispatched_at)
                        age = (datetime.now() - dt).total_seconds()
                    except (ValueError, TypeError):
                        age = STALENESS_THRESHOLD + 1
                else:
                    age = STALENESS_THRESHOLD + 1

                # Skip if still within grace period
                if age < DISPATCH_GRACE_PERIOD:
                    continue

                # Check if the session is still alive
                label = task.get("label", "")
                sandbox = task.get("sandbox", "")
                session_alive = self._is_session_alive(label, sandbox, tid, task)

                if not session_alive:
                    # Session is gone — the subagent finished (or crashed).
                    # Try to infer success from available signals.
                    outcome = self._infer_outcome(task)
                    if outcome == "completed":
                        mark_completed(tid, result="auto-detected by watcher")
                        self._sync_pipeline_manifest(
                            sandbox, tid, "completed", "auto-detected by watcher"
                        )
                        self._synced_tasks.add(tid)
                        # Track budget for auto-completed tasks
                        self._track_budget(sandbox, tid, "completed")
                        logger.info(
                            "Auto-completed stale dispatch",
                            task_id=tid,
                            label=label,
                            sandbox=sandbox,
                        )
                    elif outcome == "failed":
                        mark_failed(tid, error="session ended without result — auto-detected by watcher")
                        self._sync_pipeline_manifest(
                            sandbox, tid, "failed", "session ended without result"
                        )
                        self._synced_tasks.add(tid)
                        # Track budget for auto-failed tasks
                        self._track_budget(sandbox, tid, "failed")
                        logger.info(
                            "Auto-failed stale dispatch",
                            task_id=tid,
                            label=label,
                            sandbox=sandbox,
                        )
                    # else: "unknown" — leave as dispatched, check again next tick

    # ── Pipeline cleanup (Option C: archive on new start + stale sweep) ──

    def _cleanup_completed_pipelines(self, now: float) -> None:
        """Archive completed pipeline manifests to DLQ.

        Strategy (Option C from Kimi recommendation):
        - If a sandbox has a new pipeline AND an old completed one → archive the old one
        - If a completed pipeline is >12h old (orphaned) → archive it
        - Keeps the pipeline directory clean without losing history (DLQ)
        """
        if not PIPELINE_DIR.exists():
            return

        DLQ_DIR.mkdir(parents=True, exist_ok=True)

        # Group pipeline manifests by sandbox
        manifests_by_sandbox: dict[str, list[Path]] = {}
        for f in sorted(PIPELINE_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                sb = data.get("sandbox", "")
                if sb:
                    manifests_by_sandbox.setdefault(sb, []).append(f)
            except (json.JSONDecodeError, OSError):
                pass

        archived_count = 0

        for sandbox, files in manifests_by_sandbox.items():
            if len(files) <= 1:
                continue

            # Sort by mtime (oldest first)
            files_sorted = sorted(files, key=lambda f: f.stat().st_mtime)

            for f in files_sorted[:-1]:  # All but the newest
                try:
                    data = json.loads(f.read_text())
                    status = data.get("status", "")
                    if status in ("completed", "failed"):
                        dest = DLQ_DIR / f.name
                        f.rename(dest)
                        archived_count += 1
                        logger.info(
                            "Archived old completed pipeline",
                            sandbox=sandbox,
                            manifest=f.name,
                            dest=str(dest),
                        )
                except (json.JSONDecodeError, OSError):
                    pass

        # ── Stale sweep: archive any completed/failed pipeline >12h old ──
        # Only run this once per hour to avoid unnecessary I/O
        if now - self._last_cleanup_ts >= self._stale_sweep_interval:
            self._last_cleanup_ts = now
            stale_cutoff = now - 43200  # 12 hours
            for f in PIPELINE_DIR.glob("*.json"):
                try:
                    mtime = f.stat().st_mtime
                    if mtime < stale_cutoff:
                        data = json.loads(f.read_text())
                        status = data.get("status", "")
                        if status in ("completed", "failed"):
                            dest = DLQ_DIR / f.name
                            f.rename(dest)
                            archived_count += 1
                            logger.info(
                                "Stale sweep: archived old pipeline",
                                manifest=f.name,
                                dest=str(dest),
                            )
                except (json.JSONDecodeError, OSError):
                    pass

        if archived_count > 0:
            logger.info("Pipeline cleanup complete", archived=archived_count)

    # ── Session liveness detection ─────────────────────────────────────

    def _is_session_alive(self, label: str, sandbox: str, task_id: str, task: dict | None = None) -> bool:
        """Check whether the OpenClaw session for this dispatch is still running.

        Uses multiple signals to detect active sessions.
        Caches results for 10 seconds to avoid redundant probes.
        """
        cache_key = label or task_id
        now = time.time()

        # Return cached result if fresh
        if cache_key in self._session_cache:
            last_check = self._cache_ttl.get(cache_key, 0)
            if now - last_check < 10:
                return self._session_cache[cache_key]

        # Probe: check if there's a running OpenClaw session matching this label
        alive = self._probe_session(label, sandbox, task_id, task)

        self._session_cache[cache_key] = alive
        self._cache_ttl[cache_key] = now
        return alive

    def _probe_session(self, label: str, sandbox: str, task_id: str, task: dict | None = None) -> bool:
        """Probe for a live session matching this dispatch task.

        Strategy (checked in order):
        1. Check hero log for explicit completion/failure events
        2. Check hero log for recent session activity (< 30s ago)
        3. Check PID file for a live process
        4. Check dispatch file mtime vs dispatched_at to detect updates
        5. If no evidence of life → session is dead
        """
        now = time.time()

        # Get dispatched_at from the task for mtime comparison
        dispatched_at_ts = 0.0
        if task:
            dispatched_at = task.get("dispatched_at", "")
            if dispatched_at:
                try:
                    dispatched_at_ts = datetime.fromisoformat(dispatched_at).timestamp()
                except (ValueError, TypeError):
                    pass

        # Strategy 1: Check hero log for explicit completion/failure events
        hero_log = Path.home() / ".hero" / "logs" / "hero.jsonl"
        if hero_log.exists():
            try:
                lines = hero_log.read_text().strip().split("\n")[-200:]
                for line in reversed(lines):
                    try:
                        entry = json.loads(line)
                        entry_label = entry.get("label", "")
                        entry_tid = entry.get("task_id", "")
                        entry_event = entry.get("event", "")

                        # Explicit completion event for this task
                        if entry_event in (
                            "session_complete", "task_complete",
                            "subagent_done", "dispatch_complete",
                        ):
                            if entry_tid == task_id or entry_label == label:
                                return False  # Session definitely ended

                        # Explicit failure event
                        if entry_event in (
                            "session_failed", "task_failed",
                            "subagent_error", "dispatch_failed",
                        ):
                            if entry_tid == task_id or entry_label == label:
                                return False  # Session ended (with error)

                        # Recent activity for this task (within 30s)
                        ts = entry.get("ts", "")
                        if ts:
                            try:
                                entry_dt = datetime.fromisoformat(ts)
                                entry_age = (datetime.now() - entry_dt).total_seconds()
                                if entry_age < 30:
                                    if entry_tid == task_id or (
                                        entry.get("sandbox") == sandbox and sandbox
                                    ):
                                        return True  # Session still alive
                            except (ValueError, TypeError):
                                pass
                    except json.JSONDecodeError:
                        continue
            except OSError:
                pass

        # Strategy 2: Check if there's a .pid file for this session
        pid_dir = Path.home() / ".hero" / "sessions"
        if pid_dir.exists():
            for pid_file in pid_dir.glob("*.pid"):
                try:
                    content = pid_file.read_text().strip()
                    if label in content or task_id in content:
                        pid = int(content.split("\n")[0].strip())
                        import os
                        try:
                            os.kill(pid, 0)
                            return True  # Process is alive
                        except (OSError, ProcessLookupError):
                            return False  # Process is dead
                except (ValueError, OSError):
                    continue

        # Strategy 3: Check if dispatch file was modified AFTER dispatched_at.
        # If mtime > dispatched_at + 5s, something updated the file after dispatch
        # (possibly the session writing results). If mtime ≈ dispatched_at, the
        # file hasn't been touched since it was first written.
        dispatch_file = DISPATCH_DIR / f"{task_id}.toon"
        if not dispatch_file.exists():
            dispatch_file = DISPATCH_DIR / f"{task_id}.json"
        if dispatch_file.exists():
            try:
                mtime = dispatch_file.stat().st_mtime
                if dispatched_at_ts and mtime > dispatched_at_ts + 5:
                    # File was modified after dispatch → session may have touched it
                    file_age = now - mtime
                    if file_age < STALENESS_THRESHOLD:
                        return True  # Recently updated → session might be alive
            except OSError:
                pass

        # Strategy 4: No evidence of life found → session is dead.
        #
        # Safe because:
        # - The dispatch was already marked "dispatched" (not "pending")
        # - More than DISPATCH_GRACE_PERIOD seconds have passed
        # - No log activity, no PID file, no file updates since dispatch
        return False

    # ── Outcome inference ──────────────────────────────────────────────

    def _infer_outcome(self, task: dict) -> str:
        """Infer whether a completed session succeeded or failed.

        Looks for:
        1. Result files in the sandbox
        2. Exit markers in log files
        3. Git changes in the workdir

        Returns: "completed", "failed", or "unknown"
        """
        sandbox = task.get("sandbox", "")
        workdir = task.get("workdir", "")

        # Check for result indicators in the workdir
        if workdir:
            workdir_path = Path(workdir)
            if workdir_path.exists():
                # Check for recent git activity (commits, modified files)
                try:
                    result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=str(workdir_path),
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        # There are uncommitted changes → work was done
                        return "completed"
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    pass

                # Check for recent file modifications in the sandbox
                try:
                    recent_files = []
                    for f in workdir_path.rglob("*"):
                        if f.is_file() and not f.name.startswith("."):
                            mtime = f.stat().st_mtime
                            age = time.time() - mtime
                            if age < 300:  # Modified within 5 minutes
                                recent_files.append(f)
                    if recent_files:
                        return "completed"
                except OSError:
                    pass

        # Check hero log for explicit completion/failure markers
        hero_log = Path.home() / ".hero" / "logs" / "hero.jsonl"
        if hero_log.exists():
            try:
                lines = hero_log.read_text().strip().split("\n")[-50:]
                for line in reversed(lines):
                    try:
                        entry = json.loads(line)
                        if entry.get("task_id") == task.get("task_id"):
                            event = entry.get("event", "")
                            if "fail" in event or "error" in event:
                                return "failed"
                            if "complete" in event or "success" in event:
                                return "completed"
                    except json.JSONDecodeError:
                        continue
            except OSError:
                pass

        return "unknown"

    # ── Pipeline manifest sync ─────────────────────────────────────────

    def _sync_pipeline_manifest(
        self, sandbox: str, task_id: str, status: str, result: str
    ) -> None:
        """Update pipeline manifest soldier entry to reflect task completion.

        Scans all pipeline manifests for ones matching *sandbox*, then
        updates the soldier entry whose ``task_id`` matches.
        """
        if not PIPELINE_DIR.exists():
            return

        for manifest_file in PIPELINE_DIR.glob("*.json"):
            try:
                data = json.loads(manifest_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            if data.get("sandbox") != sandbox:
                continue

            changed = False

            # Update soldier entries
            for soldier in data.get("soldiers", []):
                if soldier.get("task_id") == task_id:
                    if soldier.get("status") != status:
                        soldier["status"] = status
                        soldier["result"] = result
                        changed = True

            # Always advance pipeline steps (handles both soldier updates
            # and recovery from stale manifests where soldiers were already synced)
            self._advance_pipeline_steps(data)
            if changed:
                try:
                    manifest_file.write_text(json.dumps(data, indent=2, default=str))
                    logger.debug(
                        "Updated pipeline manifest",
                        manifest=manifest_file.name,
                        task_id=task_id,
                        new_status=status,
                    )
                except OSError:
                    logger.exception(
                        "Failed to write pipeline manifest",
                        manifest=manifest_file.name,
                    )
            else:
                # Even if no soldier status changed, steps may still need
                # advancing (e.g., all soldiers were already completed but
                # verify/archive hadn't been activated yet).
                manifest_file.write_text(json.dumps(data, indent=2, default=str))

    @staticmethod
    def _advance_pipeline_steps(data: dict[str, Any]) -> None:
        """Advance pipeline step statuses based on current soldier states.

        Logic:
        - If all soldiers are completed → mark spawn as completed, activate verify
        - If any soldier failed → mark spawn as completed (with failures), activate fix
        - If verify done and all passed → activate archive
        """
        steps = data.get("steps", {})
        soldiers = data.get("soldiers", [])

        if not soldiers:
            return

        all_done = all(s.get("status") in ("completed", "failed") for s in soldiers)
        any_failed = any(s.get("status") == "failed" for s in soldiers)
        all_completed = all(s.get("status") == "completed" for s in soldiers)

        if all_done:
            # Mark spawn step as completed
            spawn_step = steps.get("spawn", {})
            if spawn_step.get("status") not in ("completed",):
                spawn_step["status"] = "completed"

            # If all succeeded → activate verify
            if all_completed:
                verify_step = steps.get("verify", {})
                if verify_step.get("enabled") and verify_step.get("status") in (
                    "queued", "pending", "dry_run",
                ):
                    verify_step["status"] = "active"

            # If any failed → activate fix (if enabled)
            if any_failed:
                fix_step = steps.get("fix", {})
                if fix_step.get("enabled") and fix_step.get("status") in (
                    "queued", "pending", "dry_run",
                ):
                    fix_step["status"] = "active"

        # Check if verify is done → activate archive
        verify_step = steps.get("verify", {})
        if verify_step.get("status") in ("completed", "passed"):
            archive_step = steps.get("archive", {})
            if archive_step.get("enabled") and archive_step.get("status") in (
                "queued", "pending", "dry_run",
            ):
                archive_step["status"] = "active"

        # Check if archive is done → mark pipeline completed
        archive_step = steps.get("archive", {})
        if archive_step.get("status") in ("completed", "skipped"):
            if all_completed and verify_step.get("status") in ("completed", "passed"):
                data["status"] = "completed"
                if not data.get("completed_at"):
                    data["completed_at"] = datetime.now().isoformat()

    def _track_budget(self, sandbox: str, task_id: str, status: str):
        """Update BUDGET.toon with actual or estimated usage."""
        usage = get_usage(task_id)
        if usage:
            tokens = usage["tokens_used"]
        else:
            # Estimate from dispatch data
            task = get_task(task_id)
            max_tokens = task.get("max_tokens", 8000) if task else 8000
            runtime = task.get("timeout", 300) if task else 300
            tokens = min(max_tokens, int(runtime * 10))  # ~10 tokens/sec
        
        # Write to BUDGET.toon via BudgetState
        budget_state = BudgetState(sandbox)
        budget_state.record_usage(tokens)


def start_background_watcher() -> PipelineWatcher:
    """Convenience: create and start a watcher in the background.

    Returns the watcher instance so the caller can stop it later.
    """
    watcher = PipelineWatcher()
    watcher.start()
    return watcher
