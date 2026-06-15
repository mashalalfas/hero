"""PipelineExecutor — polls dispatch queue and drives pipeline state.

Reads a pipeline manifest created by ``hero go``, monitors soldier tasks
until completion, determines overall status, and updates the manifest
at each stage.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.archivist.inline import capture_soldier, get_herolog_tail
from hero.git.branch import (
    commit_pipeline_changes,
    create_pipeline_branch,
    get_current_branch,
)
from hero.qa.gate import QAGate
from hero.reliability.circuit_breaker import is_quarantined
from hero.core.locks import FileLock
from hero.soldier.context import ContextCache
from hero.soldier.dispatch import get_task, mark_completed, mark_failed, clear_completed

PIPELINE_DIR = Path.home() / ".hero" / "pipeline"


@dataclass
class PipelineResult:
    """Result of a completed pipeline execution."""

    pipeline_id: str
    sandbox: str
    task: str
    status: str  # running | completed | failed
    soldiers: list[dict] = field(default_factory=list)
    verify_status: str | None = None
    self_review_status: str | None = None
    archive_status: str | None = None
    started_at: str = ""
    completed_at: str | None = None
    manifest_path: Path | None = None

    def summary(self) -> str:
        """Return a one-line summary string."""
        total = len(self.soldiers)
        done = sum(1 for s in self.soldiers if s["status"] == "completed")
        failed = sum(1 for s in self.soldiers if s["status"] == "failed")
        parts = [
            f"Pipeline {self.pipeline_id[:8]} — {self.status}",
            f"soldiers: {done}/{total} done",
        ]
        if failed:
            parts.append(f"{failed} failed")
        if self.self_review_status:
            parts.append(f"self-review: {self.self_review_status}")
        if self.verify_status:
            parts.append(f"verify: {self.verify_status}")
        return " | ".join(parts)


class PipelineExecutor:
    """Executes a pipeline by polling dispatch queue for task completion.

    Usage::

        executor = PipelineExecutor(manifest_path)
        result = executor.run(poll_interval=5)
        print(result.summary())
    """

    def __init__(
        self,
        manifest_path: Path,
        allowed_files: list[str] | None = None,
        max_diff_lines: int = 200,
    ) -> None:
        if not manifest_path.exists():
            raise FileNotFoundError(f"Pipeline manifest not found: {manifest_path}")

        self.manifest_path = manifest_path
        self.manifest: dict[str, Any] = json.loads(manifest_path.read_text())
        self.pipeline_id: str = self.manifest.get("pipeline_id", "unknown")
        self.sandbox: str = self.manifest.get("sandbox", "unknown")
        self.task: str = self.manifest.get("task", "unknown")

        # ── QA gate configuration (optional) ────────────────────────────
        self.allowed_files = allowed_files or []
        self.max_diff_lines = max_diff_lines

        # ── Archivist — always enabled, inline zero-cost mode ───────────
        self.archivist_enabled = True
        self.archivist_mode = "inline"

        # ── Build the list of tracked soldiers ──────────────────────────
        self.soldiers: list[dict[str, Any]] = self._build_soldiers()
        self.verify_tasks: list[dict[str, Any]] = []
        self.self_review_tasks: list[dict[str, Any]] = []
        self.archive_tasks: list[dict[str, Any]] = []

    # ── Internal helpers ────────────────────────────────────────────────

    def _build_soldiers(self) -> list[dict[str, Any]]:
        """Extract soldier entries from the manifest.

        Soldiers are identified from ``steps.dispatch.task_ids``.
        Labels are enriched from ``steps.spawn.commands`` when available.
        """
        steps = self.manifest.get("steps", {})

        # Collect all task ids from the dispatch step
        task_ids: list[str] = list(steps.get("dispatch", {}).get("task_ids", []))

        # Build a label map from spawn commands (if present)
        commands = steps.get("spawn", {}).get("commands", [])
        label_map: dict[str, str] = {}
        for cmd in commands:
            tid = cmd.get("task_id", "")
            label = cmd.get("sessions_spawn", {}).get("label", cmd.get("label", ""))
            if label:
                label_map[tid] = label

        soldiers = []
        for tid in task_ids:
            soldiers.append({
                "task_id": tid,
                "label": label_map.get(tid, tid),
                "status": "pending",
                "result": None,
            })
        return soldiers

    def _find_extra_tasks(self) -> None:
        """Extract non-soldier task IDs (verify, fix, archive) from manifest."""
        steps = self.manifest.get("steps", {})
        for phase_key, role_label in [
            ("verify", "Verify"),
            ("fix", "Fix"),
            ("self_review", "Self-Review"),
            ("archive", "Archive"),
        ]:
            phase = steps.get(phase_key, {})
            tid = phase.get("task_id")
            if tid:
                entry = {
                    "task_id": tid,
                    "label": f"{role_label} ({phase_key})",
                    "status": "pending",
                    "result": None,
                }
                if phase_key == "verify":
                    self.verify_tasks.append(entry)
                elif phase_key == "self_review":
                    self.self_review_tasks.append(entry)
                else:
                    self.archive_tasks.append(entry)

    def _status_from_dispatch(self, task_id: str) -> dict[str, Any]:
        """Read a single task's status from the dispatch queue.

        Returns a dict with task_id, status, and result.
        Defaults to ``"unknown"`` if the dispatch file is missing.
        """
        task = get_task(task_id)
        if task is None:
            return {"task_id": task_id, "status": "unknown", "result": None}
        return {
            "task_id": task_id,
            "status": task.get("status", "pending"),
            "result": task.get("result"),
        }

    def _update_manifest(
        self,
        status: str,
        soldiers: list[dict[str, Any]],
        verify_status: str | None = None,
        self_review_status: str | None = None,
        archive_status: str | None = None,
    ) -> None:
        """Persist current pipeline state to the manifest file."""
        now_iso = datetime.now().isoformat()

        self.manifest["status"] = status
        self.manifest["soldiers"] = soldiers

        if verify_status is not None:
            self.manifest["verify_status"] = verify_status
        if self_review_status is not None:
            self.manifest["self_review_status"] = self_review_status
        if archive_status is not None:
            self.manifest["archive_status"] = archive_status

        if status == "running" and not self.manifest.get("started_at"):
            self.manifest["started_at"] = now_iso
        if status in ("completed", "failed", "verify_failed") and not self.manifest.get(
            "completed_at"
        ):
            self.manifest["completed_at"] = now_iso

        with FileLock("pipeline_manifest"):
            self.manifest_path.write_text(json.dumps(self.manifest, indent=2, default=str))

    def _poll_tasks(
        self, tasks: list[dict[str, Any]], poll_interval: int, max_wait: int = 600
    ) -> None:
        """Poll a list of tasks until all are in a terminal state.

        Mutates ``tasks`` in place with updated status/result.
        Raises ``TimeoutError`` if ``max_wait`` seconds elapses.
        """
        deadline = time.time() + max_wait

        while True:
            if time.time() > deadline:
                raise TimeoutError(
                    f"Pipeline {self.pipeline_id[:8]} — polling timed out "
                    f"after {max_wait}s"
                )

            all_done = True
            for task in tasks:
                info = self._status_from_dispatch(task["task_id"])
                s = info["status"]
                if s in ("completed", "failed"):
                    task["status"] = s
                    task["result"] = info.get("result")
                elif s in ("unknown",):
                    # Treat unknown as still pending — might be slow to write
                    task["status"] = "pending"
                    all_done = False
                else:
                    task["status"] = s
                    all_done = False

            if all_done:
                break

            self._update_manifest("running", self.soldiers)
            time.sleep(poll_interval)

    # ── Public API ──────────────────────────────────────────────────────

    def _load_shared_context(self, cache: ContextCache) -> dict[str, str]:
        """Load shared project context using the ContextCache.

        Reads common project files (README.md, PLAN.md, package config)
        from the sandbox path so every soldier doesn't re-read them.

        Args:
            cache: A ContextCache instance reused across the pipeline.

        Returns:
            Dict of cached context keyed by label (e.g. "README", "PLAN").
        """
        sandbox_path = Path(self.sandbox)
        if not sandbox_path.is_absolute():
            sandbox_path = Path.home() / "Development" / self.sandbox

        shared: dict[str, str] = {}

        # Common project context files
        for key, filename in [
            ("README", "README.md"),
            ("PLAN", "PLAN.md"),
            ("package.json", "package.json"),
            ("pubspec.yaml", "pubspec.yaml"),
            ("pyproject.toml", "pyproject.toml"),
            ("Cargo.toml", "Cargo.toml"),
        ]:
            content = cache.get_or_load(key, sandbox_path / filename, max_chars=2000)
            if content:
                shared[key] = content

        return shared

    def update_soldier_status(
        self,
        task_id: str,
        status: str,
        result: str = "",
    ) -> bool:
        """Update a soldier's status in both dispatch and manifest.

        Call this when a subagent completion event arrives so the
        pipeline state stays in sync without waiting for the poll loop.

        Args:
            task_id: The dispatch task ID.
            status:   New status ("completed" or "failed").
            result:   Optional result/error summary.

        Returns:
            True if the soldier was found and updated.
        """
        # Update dispatch file
        if status == "completed":
            mark_completed(task_id, result=result)
        elif status == "failed":
            mark_failed(task_id, error=result)

        # Update in-memory soldier list
        updated = False
        for soldier in self.soldiers:
            if soldier.get("task_id") == task_id:
                soldier["status"] = status
                soldier["result"] = result
                updated = True
                break

        # Also check verify / self-review / archive tasks
        for task_list in (self.verify_tasks, self.self_review_tasks, self.archive_tasks):
            for t in task_list:
                if t.get("task_id") == task_id:
                    t["status"] = status
                    t["result"] = result
                    updated = True

        if updated:
            # Persist to manifest
            soldier_failures = [s for s in self.soldiers if s["status"] == "failed"]
            manifest_status = "failed" if soldier_failures else "running"
            self._update_manifest(manifest_status, self.soldiers)

        return updated

    def run(
        self,
        poll_interval: int = 5,
        max_wait: int = 600,
    ) -> PipelineResult:
        """Execute the pipeline and return a ``PipelineResult``.

        Stages:
        1. Start — mark manifest as ``running``
        2. Context cache — load shared project context for dedup
        3. Soldier phase — poll soldier tasks until done
        4. Verify phase — if all soldiers succeeded, check verify task
        5. Archive phase — check archive task if verify passed
        6. Final status — ``completed`` | ``failed`` | ``verify_failed``
        """
        # ── Stage 0: Circuit breaker gate ────────────────────────────
        if is_quarantined(self.sandbox):
            raise RuntimeError(
                f"Sandbox '{self.sandbox}' is quarantined. "
                f"Use 'hero sandbox unquarantine {self.sandbox}' first."
            )

        # ── Stage 0a: Context cache — shared across all soldiers ────
        context_cache = ContextCache()
        shared_context = self._load_shared_context(context_cache)

        started_at = datetime.now().isoformat()

        # Identify extra tasks (verify, fix, archive)
        self._find_extra_tasks()

        # ── Stage 1: Start ──────────────────────────────────────────────
        self._update_manifest("running", self.soldiers)

        # ── Stage 1a: QA gate — pre-flight validation ────────────────────
        sandbox_path = Path(self.sandbox)
        if not sandbox_path.is_absolute():
            sandbox_path = Path.cwd() / self.sandbox

        if self.allowed_files and sandbox_path.exists():
            qa_gate = QAGate(
                sandbox_path=sandbox_path,
                allowed_files=self.allowed_files,
                max_diff_lines=self.max_diff_lines,
            )
            qa_result = qa_gate.run()
            if not qa_result.passed:
                # Send all queued soldier tasks to DLQ
                for soldier in self.soldiers:
                    task_id = soldier.get("task_id", "unknown")
                    qa_gate.handle_failure(
                        qa_result,
                        task_id,
                        {"sandbox": self.sandbox, "task": task_id},
                    )
                raise RuntimeError(
                    f"QA gate rejected sandbox '{self.sandbox}': "
                    f"{'; '.join(qa_result.violations)}"
                )

        # ── Git: create pipeline branch (if auto-commit enabled) ──────
        if self.manifest.get("auto_commit", False):
            try:
                svp = Path(self.sandbox)
                if not svp.is_absolute():
                    svp = Path.cwd() / self.sandbox
                self.manifest["original_branch"] = get_current_branch(svp)
                self.manifest["pipeline_branch"] = create_pipeline_branch(
                    svp, self.pipeline_id
                )
                # Persist branch info to manifest immediately
                with FileLock("pipeline_manifest"):
                    self.manifest_path.write_text(
                        json.dumps(self.manifest, indent=2, default=str)
                    )
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                raise RuntimeError(
                    f"Git branch creation failed for sandbox "
                    f"'{self.sandbox}': {exc}"
                ) from exc

        # ── Stage 2: Poll soldier tasks ─────────────────────────────────
        if self.soldiers:
            self._poll_tasks(self.soldiers, poll_interval, max_wait)

        # ── Stage 2a: Archivist — capture soldier results ────────────────
        if self.archivist_enabled:
            pipeline_dir = PIPELINE_DIR / self.pipeline_id
            journal_path = pipeline_dir / "HEROLOG.md"
            diffs_path = pipeline_dir / "soldier_diffs.md"
            for soldier in self.soldiers:
                capture_soldier(
                    pipeline_id=self.pipeline_id,
                    sandbox=self.sandbox,
                    task_id=soldier.get("task_id", "?"),
                    soldier_label=soldier.get("label", soldier.get("task_id", "?")),
                    status=soldier.get("status", "unknown"),
                    result=soldier.get("result"),
                    journal_path=journal_path,
                    diffs_path=diffs_path,
                )

        soldier_failures = [s for s in self.soldiers if s["status"] == "failed"]
        if soldier_failures:
            status = "failed"
            verify_status = None
            self_review_status = None
            archive_status = None
            self._update_manifest(status, self.soldiers)
        else:
            # ── Stage 2b: Self-Review — between archivist and verify ────
            self_review_status = None
            if self.self_review_tasks:
                self._poll_tasks(
                    self.self_review_tasks, poll_interval, max_wait // 5
                )
                sr_failures = [
                    t for t in self.self_review_tasks if t["status"] == "failed"
                ]
                self_review_status = "failed" if sr_failures else "passed"
            else:
                self_review_status = "passed"  # no self-review = auto-pass

            # ── Stage 3: Verify tasks ───────────────────────────────────
            verify_status = None
            if self.verify_tasks:
                self._poll_tasks(self.verify_tasks, poll_interval, max_wait // 3)
                verify_failures = [t for t in self.verify_tasks if t["status"] == "failed"]
                verify_status = "failed" if verify_failures else "passed"
            else:
                verify_status = "passed"  # no verify = auto-pass

            # ── Stage 4: Archive tasks ──────────────────────────────────
            archive_status = None
            if verify_status == "passed" and self.archive_tasks:
                self._poll_tasks(self.archive_tasks, poll_interval, max_wait // 4)
                archive_failures = [t for t in self.archive_tasks if t["status"] == "failed"]
                archive_status = "failed" if archive_failures else "completed"
            elif verify_status == "passed":
                archive_status = "skipped"
            else:
                archive_status = "skipped"

            if verify_status == "failed":
                status = "verify_failed"
            else:
                status = "completed"

            self._update_manifest(
                status,
                self.soldiers,
                verify_status=verify_status,
                self_review_status=self_review_status,
                archive_status=archive_status,
            )

        # ── Git: commit changes if pipeline succeeded ──────────────────
        if status == "completed" and self.manifest.get("auto_commit", False):
            try:
                svp = Path(self.sandbox)
                if not svp.is_absolute():
                    svp = Path.cwd() / self.sandbox
                commit_pipeline_changes(
                    svp,
                    f"Pipeline {self.pipeline_id}: {self.task}",
                )
            except subprocess.CalledProcessError:
                # Non-fatal — pipeline already completed
                pass

        return PipelineResult(
            pipeline_id=self.pipeline_id,
            sandbox=self.sandbox,
            task=self.task,
            status=status,
            soldiers=self.soldiers,
            verify_status=verify_status,
            self_review_status=self_review_status,
            archive_status=archive_status,
            started_at=started_at,
            completed_at=datetime.now().isoformat()
            if status in ("completed", "failed", "verify_failed")
            else None,
            manifest_path=self.manifest_path,
        )
