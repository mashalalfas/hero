"""hero.viewport.tree — Army tree view data structures.

Builds a command-hierarchy tree from pipeline manifests and dispatch files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.viewport import states as state_defs

PIPELINE_DIR = Path.home() / ".hero" / "pipeline"
DISPATCH_DIR = Path.home() / ".hero" / "dispatch"

# ── Status icon/colour mapping ───────────────────────────────────────────────

_STATUS_META: dict[str, tuple[str, str]] = {
    # (icon, rich colour)
    "active":   ("●", "cyan"),
    "running":  ("●", "cyan"),
    "working":  ("●", "cyan"),
    "idle":     ("○", "blue"),
    "dispatched": ("◌", "yellow"),
    "pending":  ("◌", "yellow"),
    "queued":   ("◌", "yellow"),
    "done":     ("✓", "green"),
    "completed": ("✓", "green"),
    "error":    ("✗", "red"),
    "failed":   ("✗", "red"),
    "timeout":  ("✗", "red"),
    "blocked":  ("⊘", "red"),
    "retry":    ("🔄", "yellow"),
    "fixing":   ("●", "yellow"),
    "archiving": ("◑", "yellow"),
    "spawning":  ("◌", "yellow"),
    "booting":   ("◌", "yellow"),
    "completing": ("◑", "yellow"),
    "dead":      ("○", "grey50"),
    "created":  ("✓", "green"),
    "skipped":  ("○", "blue"),
    "brainstorm": ("●", "cyan"),
    "worktree":   ("●", "cyan"),
    "analysis":   ("●", "yellow"),
    "verify_fix": ("🔄", "yellow"),
}


def _status_icon(status: str) -> tuple[str, str]:
    """Return (icon, colour) for a given status string."""
    s = (status or "idle").lower()
    return _STATUS_META.get(s, ("?", "white"))


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class TreeNode:
    """A single node in the army command tree."""

    role: str              # COMM, LEAD, ARCH, SOLDIER, VERIFY, ARCHIVIST, RETRY
    name: str              # display name (e.g. sandbox-soldier-1, task short label)
    status: str            # active / done / queued / error / retry / blocked …
    model: str | None = None
    task: str | None = None
    children: list[TreeNode] = field(default_factory=list)
    is_error: bool = False
    error_detail: str | None = None
    retry_count: int = 0


@dataclass
class PipelineState:
    """Snapshot of an entire pipeline for one sandbox."""

    sandbox_name: str
    task: str
    root_node: TreeNode
    active: bool
    created_at: datetime | None = None


# ── Pipeline reading ─────────────────────────────────────────────────────────


def _load_pipeline_manifest(sandbox_name: str) -> dict | None:
    """Load pipeline JSON by sandbox name from ~/.hero/pipeline/.

    Always reads fresh from disk so watcher-updated manifests
    are reflected immediately in the viewport.
    """
    if not PIPELINE_DIR.exists():
        return None
    # Match by sandbox name field inside the JSON, not filename.
    for f in PIPELINE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("sandbox") == sandbox_name:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _load_dispatch_files(sandbox_name: str) -> dict[str, dict]:
    """Load all dispatch files for a sandbox, keyed by task_id.

    Always reads fresh from disk (no caching) so the viewport
    reflects watcher-updated state immediately.
    """
    result: dict[str, dict] = {}
    if not DISPATCH_DIR.exists():
        return result
    for f in DISPATCH_DIR.glob("*.toon"):
        try:
            data = _parse_viewport_toon(f.read_text())
            if data and data.get("sandbox") == sandbox_name:
                tid = data.get("task_id") or f.stem
                result[tid] = data
        except Exception:
            pass
    for f in DISPATCH_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data and data.get("sandbox") == sandbox_name:
                tid = data.get("task_id") or f.stem
                result[tid] = data
        except Exception:
            pass
    return result


def _parse_viewport_toon(content: str) -> dict | None:
    """Parse a TOON dispatch entry back into a dict."""
    import re
    result: dict[str, Any] = {}
    for line in content.strip().split("\n"):
        line = line.rstrip()
        if not line:
            continue
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val == "null":
                val = None
            elif val == "true":
                val = True
            elif val == "false":
                val = False
            else:
                try:
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
            result[key] = val
    return result if result else None


# ── Tree builder ─────────────────────────────────────────────────────────────


def build_tree(
    sandbox_name: str,
    sandbox_data: dict,
    dispatch_data: dict | None = None,
    manifest: dict | None = None,
) -> TreeNode:
    """Build a command-hierarchy tree for one sandbox/pipeline.

    Parameters
    ----------
    sandbox_name:
        Name of the sandbox (used to look up pipeline manifest and dispatches).
    sandbox_data:
        Raw cache dict for this sandbox (from ``StateCache``).
    dispatch_data:
        Optional pre-loaded dispatch map {task_id: dispatch_dict}.  When
        *None* the function reads files from ``~/.hero/dispatch/`` itself.
    manifest:
        Optional pre-loaded pipeline manifest dict.  When *None* the function
        reads it from ``~/.hero/pipeline/``.

    Returns
    -------
    TreeNode
        Root node of the army tree with all pipeline phases attached.
    """
    if dispatch_data is None:
        dispatch_data = _load_dispatch_files(sandbox_name)

    if manifest is None:
        manifest = _load_pipeline_manifest(sandbox_name)

    soldiers, verify_task, fix_task, archive_task, report_task, brainstorm_data, worktree_data, analysis_data, verify_fix_loop_data = _extract_pipeline_nodes(
        manifest, dispatch_data
    )

    # ── Build tree ─────────────────────────────────────────────────────────
    #   COMM (root)
    #   ├── BRAINSTORM(0)   — optional
    #   ├── WORKTREE(0b)    — always
    #   ├── ANALYSIS(1)     — always
    #   ├── LEAD(2)
    #   │   └── ARCH
    #   │       ├── SOLDIERS(3)
    #   │       │   └── RETRY (×N if errors)
    #   │       ├── VERIFY_FIX(4→5) — loop
    #   │       └── ARCHIVIST(6)
    #   └── COMM(report)(7)

    # Root COMM (pipeline coordinator)
    comm_status, comm_icon, comm_color = _resolve_status(
        manifest.get("status", "queued") if manifest else "queued",
        manifest is not None,
    )
    comm_node = TreeNode(
        role="COMM",
        name=sandbox_name,
        status=comm_status,
        model=None,
        task=manifest.get("task") if manifest else None,
        children=[],
    )

    # ── BRAINSTORM node (optional) ─────────────────────────────────────────
    if brainstorm_data:
        bs_skills = brainstorm_data.get("matched_skills", 0)
        bs_task = (
            f"{bs_skills} skill{'s' if bs_skills != 1 else ''} matched"
            if brainstorm_data.get("status") in ("done", "completed")
            else "Matching skills…"
        )
        brainstorm_node = TreeNode(
            role="BRAINSTORM",
            name=f"Brainstorm ({bs_skills})",
            status=brainstorm_data.get("status", "queued"),
            model=None,
            task=bs_task,
        )
        comm_node.children.append(brainstorm_node)

    # ── WORKTREE node (always) ─────────────────────────────────────────────
    worktree_status = worktree_data.get("status", "queued") if worktree_data else "queued"
    if worktree_data and worktree_data.get("branch") and worktree_data.get("path"):
        wt_task = f"{worktree_data['branch']} \u2192 {worktree_data['path']}"
    else:
        wt_task = "Setting up worktree…"
    worktree_node = TreeNode(
        role="WORKTREE",
        name="Worktree",
        status=worktree_status,
        model=worktree_data.get("model") if worktree_data else None,
        task=wt_task,
    )
    comm_node.children.append(worktree_node)

    # ── ANALYSIS node (always) ─────────────────────────────────────────────
    analysis_status = analysis_data.get("status", "queued") if analysis_data else "queued"
    if analysis_data:
        pt = analysis_data.get("project_type", "?")
        ec = analysis_data.get("exit_code")
        analysis_detail = f"{pt}: exit={ec}" if ec is not None else pt
    else:
        analysis_detail = "Analysing project…"
    analysis_node = TreeNode(
        role="ANALYSIS",
        name="Analysis",
        status=analysis_status,
        model=None,
        task=analysis_detail,
    )
    comm_node.children.append(analysis_node)

    # ── LEAD node (breakdown / planning) ───────────────────────────────────
    lead_status = (
        "done"
        if manifest and manifest.get("steps", {}).get("analysis", {}).get("status") == "done"
        else "queued"
    )
    lead_node = TreeNode(
        role="LEAD",
        name="Breakdown",
        status=lead_status,
        model=None,
        task=manifest.get("task") if manifest else None,
        children=[],
    )
    comm_node.children.append(lead_node)

    # ── ARCH node (orchestration hub) ──────────────────────────────────────
    arch_node = TreeNode(
        role="ARCH",
        name="Orchestrate",
        status=_arch_status(manifest),
        model=None,
        task="Verify \u2192 Fix \u2192 Archive",
        children=[],
    )
    lead_node.children.append(arch_node)

    # ── SOLDIERS (parallel workers from spawn step) ─────────────────────────
    if soldiers:
        for sd in soldiers:
            soldier_status = _soldier_status(sd)
            soldier_node = TreeNode(
                role="SOLDIER",
                name=sd.get("label", sd.get("task_id", "unknown")),
                status=soldier_status,
                model=sd.get("model"),
                task=sd.get("task", "")[:80] if sd.get("task") else None,
                is_error=(soldier_status in ("error", "failed", "timeout")),
                error_detail=sd.get("result") if soldier_status in ("error", "failed", "timeout") else None,
                retry_count=0,
            )
            arch_node.children.append(soldier_node)

            # Error forking: retry branch off failed soldiers
            if soldier_status in ("error", "failed", "timeout") and fix_task:
                retry_node = TreeNode(
                    role="RETRY",
                    name="RETRY 1",
                    status="active",
                    model=fix_task.get("model"),
                    task=fix_task.get("task", "")[:80],
                    retry_count=1,
                )
                soldier_node.children.append(retry_node)
    else:
        arch_node.children.append(TreeNode(
            role="SOLDIER",
            name="(none)",
            status="queued",
            model=None,
            task="Waiting for spawn",
        ))

    # ── VERIFY_FIX loop node ───────────────────────────────────────────────
    if verify_fix_loop_data and verify_fix_loop_data.get("tasks"):
        vfl_status = verify_fix_loop_data.get("final_status", "queued")
        iterations = verify_fix_loop_data.get("iterations", 0)
        iter_label = f"{iterations} iter{'s' if iterations != 1 else ''}" if iterations > 0 else "awaiting"
        vfl_node = TreeNode(
            role="VERIFY_FIX",
            name=f"Verify\u21d4Fix ({iter_label})",
            status=vfl_status,
            model=None,
            task=f"{iterations} iteration{'s' if iterations != 1 else ''}" if iterations > 0 else "Awaiting verification",
            children=[],
        )
        for i, t in enumerate(verify_fix_loop_data.get("tasks", [])):
            role_name = "VERIFY" if i % 2 == 0 else "FIX"
            iter_node = TreeNode(
                role=role_name,
                name=f"Iteration {i+1}",
                status=t.get("status", "queued"),
                model=t.get("model"),
                task=t.get("task", "")[:80] if t.get("task") else None,
            )
            vfl_node.children.append(iter_node)
    else:
        # Fallback: single VERIFY + FIX pair from old-style manifest
        vfl_node = TreeNode(
            role="VERIFY_FIX",
            name="Verify\u21d4Fix",
            status=verify_task.get("status", "queued") if verify_task else "queued",
            model=None,
            task="Verify soldier output",
            children=[],
        )
        if verify_task:
            vfl_node.children.append(TreeNode(
                role="VERIFY",
                name=verify_task.get("label", "verify"),
                status=verify_task.get("status", "queued"),
                model=verify_task.get("model"),
                task="Verify soldier output",
            ))
        if fix_task:
            vfl_node.children.append(TreeNode(
                role="FIX",
                name=fix_task.get("label", "fix"),
                status=fix_task.get("status", "queued"),
                model=fix_task.get("model", "custom-api-canopywave-io/moonshotai/kimi-k2.6"),
                task=fix_task.get("task", "")[:80],
            ))

    arch_node.children.append(vfl_node)

    # ── ARCHIVIST node ─────────────────────────────────────────────────────
    archive_status = archive_task.get("status", "queued") if archive_task else "queued"
    archive_node = TreeNode(
        role="ARCHIVIST",
        name=archive_task.get("label", "archive") if archive_task else "archive",
        status=archive_status,
        model=archive_task.get("model") if archive_task else None,
        task="Archive results",
    )
    arch_node.children.append(archive_node)

    # ── REPORT COMM node (sibling of LEAD under root COMM) ─────────────────
    report_status = "queued"
    if report_task:
        report_status = report_task.get("status", "queued")
    elif archive_status == "done":
        report_status = "active"
    report_node = TreeNode(
        role="COMM",
        name="Report",
        status=report_status,
        model=None,
        task="Summarise to user",
    )
    comm_node.children.append(report_node)

    return comm_node


# ── Pipeline data extraction ─────────────────────────────────────────────────


def _extract_pipeline_nodes(
    manifest: dict | None,
    dispatch_data: dict[str, dict],
) -> tuple[list[dict], dict | None, dict | None, dict | None, dict | None, dict | None, dict | None, dict | None, dict | None]:
    """Extract soldier dispatch records and phase tasks from pipeline data.

    Returns
    -------
    tuple of (soldiers, verify_task, fix_task, archive_task, report_task,
              brainstorm_data, worktree_data, analysis_data, verify_fix_loop_data)
    """
    soldiers: list[dict] = []
    verify_task: dict | None = None
    fix_task: dict | None = None
    archive_task: dict | None = None
    report_task: dict | None = None
    brainstorm_data: dict | None = None
    worktree_data: dict | None = None
    analysis_data: dict | None = None
    verify_fix_loop_data: dict | None = None

    if manifest:
        steps = manifest.get("steps", {})

        # Soldiers from manifest.soldiers
        for sd in manifest.get("soldiers", []):
            tid = sd.get("task_id")
            if tid and tid in dispatch_data:
                merged = dict(dispatch_data[tid])
                merged.update(sd)
                soldiers.append(merged)
            else:
                soldiers.append(sd)

        # ── Phase data from manifest.steps ──────────────────────
        bs_step = steps.get("brainstorm", {})
        if bs_step:
            brainstorm_data = {
                "status": bs_step.get("status", "queued"),
                "matched_skills": len(bs_step.get("matched_skills", [])),
            }

        wt_step = steps.get("worktree", {})
        if wt_step:
            worktree_data = {
                "status": wt_step.get("status", "queued"),
                "path": wt_step.get("path"),
                "branch": wt_step.get("branch"),
                "model": wt_step.get("model"),
            }

        an_step = steps.get("analysis", {})
        if an_step:
            analysis_data = {
                "status": an_step.get("status", "queued"),
                "project_type": an_step.get("project_type"),
                "exit_code": an_step.get("exit_code"),
            }

        vfl_step = steps.get("verify_fix_loop", {})
        if vfl_step:
            verify_fix_loop_data = {
                "iterations": vfl_step.get("iterations", 0),
                "final_status": vfl_step.get("final_status", "queued"),
                "circuit_breaker_triggered": vfl_step.get("circuit_breaker_triggered", False),
                "tasks": vfl_step.get("tasks", []),
            }

        # Communicator instructions tells us task IDs for each phase
        comm_instructions = manifest.get("communicator_instructions", "")
        if isinstance(comm_instructions, str):
            import re
            verify_match = re.search(r'verify task[:\s]+(\S+)', comm_instructions, re.IGNORECASE)
            fix_match = re.search(r'fix task[:\s]+(\S+)', comm_instructions, re.IGNORECASE)
            archive_match = re.search(r'archive task[:\s]+(\S+)', comm_instructions, re.IGNORECASE)
            if verify_match:
                tid = verify_match.group(1).strip()
                verify_task = dispatch_data.get(tid, {"task_id": tid, "status": "queued", "label": "verify"})
            if fix_match:
                tid = fix_match.group(1).strip()
                fix_task = dispatch_data.get(tid, {"task_id": tid, "status": "queued", "label": "fix", "model": "custom-api-canopywave-io/moonshotai/kimi-k2.6"})
            if archive_match:
                tid = archive_match.group(1).strip()
                archive_task = dispatch_data.get(tid, {"task_id": tid, "status": "queued", "label": "archive"})

        # Fallback: steps.verify, steps.fix, steps.archive (old-style)
        if not verify_task and steps.get("verify", {}).get("enabled"):
            verify_step = steps.get("verify", {})
            verify_task = {
                "status": verify_step.get("status", "queued"),
                "label": "verify",
            }
        if not fix_task and steps.get("fix", {}).get("enabled"):
            fix_step = steps.get("fix", {})
            fix_task = {
                "status": fix_step.get("status", "queued"),
                "label": "fix",
                "model": fix_step.get("model", "custom-api-canopywave-io/moonshotai/kimi-k2.6"),
                "task_id": fix_step.get("task_id"),
            }
        if not archive_task and steps.get("archive", {}).get("enabled"):
            archive_step = steps.get("archive", {})
            archive_task = {"status": archive_step.get("status", "queued"), "label": "archive"}

        # Report step
        if steps.get("report", {}).get("status") == "pending":
            report_task = {"status": "pending", "label": "report"}
    else:
        # No manifest — fall back to dispatch files by role
        for tid, data in dispatch_data.items():
            role = (data.get("role") or "").lower()
            if role == "soldier":
                soldiers.append(data)
            elif "verify" in tid or role == "utility":
                if verify_task is None:
                    verify_task = data
            elif "fix" in tid:
                fix_task = data
            elif "archive" in tid or role == "archivist":
                archive_task = data

    return soldiers, verify_task, fix_task, archive_task, report_task, brainstorm_data, worktree_data, analysis_data, verify_fix_loop_data


# ── Status helpers ───────────────────────────────────────────────────────────


def _resolve_status(manifest_status: str, has_manifest: bool) -> tuple[str, str, str]:
    """Return (status, icon, colour) for the pipeline root."""
    base = manifest_status.lower()
    icon, color = _status_icon(base)
    if not has_manifest:
        return "queued", icon, color
    return base, icon, color


def _arch_status(manifest: dict | None) -> str:
    """Derive the ARCH node status from pipeline steps."""
    if not manifest:
        return "queued"
    steps = manifest.get("steps", {})
    # ARCH is active if any of verify/fix/archive are in progress
    for phase in ("verify", "fix", "archive"):
        st = steps.get(phase, {}).get("status", "")
        if st in ("active", "running", "working"):
            return "active"
        if st in ("queued", "pending"):
            return "queued"
    return "done"


def _soldier_status(sd: dict) -> str:
    """Derive soldier status from dispatch data."""
    raw = sd.get("status", "idle")
    r = raw.lower()
    if r in ("done", "completed", "success"):
        return "done"
    if r in ("error", "failed", "timeout"):
        return "error"
    if r in ("running", "active"):
        return "active"
    return "queued"


# ── Public builder (tree → PipelineState) ────────────────────────────────────


def build_pipeline_state(
    sandbox_name: str,
    sandbox_data: dict,
    dispatch_data: dict | None = None,
) -> PipelineState:
    """Convenience wrapper: build tree and wrap in ``PipelineState``."""
    root = build_tree(sandbox_name, sandbox_data, dispatch_data)
    manifest = _load_pipeline_manifest(sandbox_name)
    active = manifest is not None and manifest.get("status", "dead") != "dead"
    created_at = None
    if manifest:
        ts = manifest.get("started_at") or manifest.get("created_at")
        if ts:
            try:
                created_at = datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                pass
    return PipelineState(
        sandbox_name=sandbox_name,
        task=manifest.get("task", "") if manifest else "",
        root_node=root,
        active=active,
        created_at=created_at,
    )
