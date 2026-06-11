"""hero orchestrate -- Lead agent coordinates the army."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import click

from hero.prompts import render_template
from hero.soldier.dispatch import enqueue
from hero.soldier.spawner import estimate_budget, load_army_config, get_model_for_role
from hero.state.index import IndexState

# Pattern for model-output subtask lines: "[N] [sandbox] description"
_SUBTASK_RE = re.compile(r"^\s*\[(\d+)\]\s*\[([^\]]+)\]\s+(.+)$", re.MULTILINE)


@click.command()
@click.option("--sandbox", required=True, type=str, help="Target sandbox name.")
@click.option("--task", required=True, type=str, help="High-level task description.")
@click.option("--budget", type=int, default=None, help="Budget per soldier (auto-estimated from task complexity if not set).")
def orchestrate(sandbox: str, task: str, budget: int) -> None:
    """Lead agent orchestrates army execution for a sandbox."""
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        raise click.ClickException(f"Sandbox '{sandbox}' not found.")

    sandbox_path = Path(entry["path"])
    if not sandbox_path.exists():
        raise click.ClickException(f"Path does not exist: {sandbox_path}")

    lead_model, lead_provider = get_model_for_role("lead")
    soldier_model, soldier_provider = get_model_for_role("soldier")

    click.echo("")
    click.echo("=" * 60)
    click.echo("LEAD AGENT -- Army Orchestration")
    click.echo("=" * 60)
    click.echo(f"  Sandbox:   {sandbox}")
    click.echo(f"  Task:      {task}")
    click.echo(f"  Lead:      {lead_model} ({lead_provider})")
    click.echo(f"  Soldiers:  {soldier_model} ({soldier_provider})")
    click.echo(f"  Budget:    {budget if budget is not None else 'auto'} tokens per soldier")
    click.echo("=" * 60)

    # Scan sandbox
    click.echo("")
    click.echo("Analyzing sandbox...")

    ts_files = list(sandbox_path.rglob("*.tsx")) + list(sandbox_path.rglob("*.ts"))
    css_files = list(sandbox_path.rglob("*.css"))
    dart_files = list(sandbox_path.rglob("*.dart")) if (sandbox_path / "pubspec.yaml").exists() else []
    test_files = [f for f in (ts_files + dart_files) if "test" in f.name.lower()]

    click.echo(f"  TypeScript files: {len(ts_files)}")
    click.echo(f"  CSS files:        {len(css_files)}")
    if dart_files:
        click.echo(f"  Dart files:       {len(dart_files)}")
    click.echo(f"  Test files:       {len(test_files)}")

    # Check for errors
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        result = None

    errors = []
    if result and result.returncode != 0:
        for line in result.stderr.strip().splitlines():
            if "error TS" in line:
                errors.append(line.strip())

    if errors:
        click.echo(f"  TypeScript errors: {len(errors)}")
        for e in errors[:5]:
            click.echo(f"    {e}")
    else:
        click.echo("  No TypeScript errors.")

    # ── Dynamic budget estimation ──────────────────────────────────────
    if budget is None:
        # Count source files from src_map for project_size
        project_size = sum(len(files) for files in _get_src_map(sandbox_path).values())
        budget = estimate_budget(task, files=[], project_size=project_size)
        click.echo(f"  Auto-estimated budget: {budget} tokens (project size: {project_size} files)")
    click.echo("")

    # ── LLM-based task decomposition via Lead model ──────────────────────
    click.echo("Consulting Lead agent for task decomposition...")
    llm_subtasks = _call_lead_model(task, sandbox, str(sandbox_path), lead_model)

    if llm_subtasks:
        click.echo(f"  Lead returned {len(llm_subtasks)} subtask(s).")
        subtasks = llm_subtasks
    else:
        click.echo("  Lead returned no subtasks; falling back to heuristic analysis.")
        subtasks = _analyze_task(task, errors, sandbox, sandbox_path, soldier_model)

    if not subtasks:
        click.echo("  ⚠ No subtasks derived. Falling back to single task.")
        subtasks = [{
            "title": "Execute task",
            "goal": task,
            "files": "auto-detected from analysis",
            "model": soldier_model,
        }]

    for i, st in enumerate(subtasks, 1):
        click.echo(f"")
        click.echo(f"  [{i}] {st['title']}")
        click.echo(f"      Files: {st['files']}")
        desc = st['goal'][:100] + ("..." if len(st['goal']) > 100 else "")
        click.echo(f"      Goal: {desc}")

    # Queue subtasks
    click.echo("")
    click.echo(f"Queuing {len(subtasks)} subtasks...")

    for st in subtasks:
        task_id = enqueue(
            sandbox=sandbox,
            task=st["goal"],
            model=st["model"],
            budget=budget,
            workdir=str(sandbox_path),
            timeout=300,
            max_tokens=min(budget, 20000),
        )
        click.echo(f"  [\u2713] {task_id} — {st['title']}")

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"ARMY READY -- {len(subtasks)} soldiers queued")
    click.echo("=" * 60)
    click.echo("")
    click.echo("Next step:")
    click.echo("  hero dispatch spawn   (execute all queued tasks)")
    click.echo("")


def _read_plan(sandbox_path: Path) -> str:
    """Read PLAN.md if it exists."""
    plan_file = sandbox_path / "PLAN.md"
    if plan_file.exists():
        return plan_file.read_text()
    return ""


def _get_src_map(sandbox_path: Path) -> dict[str, list[dict]]:
    """Build a map of source files by directory.

    Supports: .dart, .ts, .tsx, .js, .jsx, .css
    """
    supported = (".dart", ".ts", ".tsx", ".css", ".js", ".jsx")

    # Flutter projects use lib/ not src/
    src = sandbox_path / "src" if not (sandbox_path / "pubspec.yaml").exists() else sandbox_path / "lib"
    if not src.exists():
        return {}
    result: dict[str, list[dict]] = {}
    for f in sorted(src.rglob("*")):
        if f.is_file() and f.suffix in supported:
            rel = f.relative_to(sandbox_path)
            parts = str(rel.parent)
            result.setdefault(parts, []).append({
                "name": f.name,
                "path": str(rel),
                "size": f.stat().st_size,
            })
    return result


def _estimate_tokens(path: Path) -> int:
    """Estimate token cost of a file."""
    if not path.exists():
        return 0
    lines = len(path.read_text().splitlines())
    return 5000 + (lines // 100) * 2000


def _call_lead_model(task: str, sandbox: str, workdir: str, lead_model: str) -> list[dict] | None:
    """Ask the Lead model to decompose the task into subtasks.

    Returns a list of subtask dicts on success, or None on failure
    (caller should fall back to heuristic analysis).
    """
    from hero.soldier.spawner import get_model_for_role
    _soldier_model, _ = get_model_for_role("soldier")
    try:
        # Build prompt from lead role template
        prompt = render_template(
            "roles/lead.md",
            sandbox=sandbox,
            workdir=workdir,
            model=lead_model,
            context_window="600",
            extra_rules=(
                "TASK:\n"
                f"  Decompose this task into 2-6 focused subtasks:\n"
                f"  {task}\n\n"
                "OUTPUT FORMAT (one line per subtask, no preamble, no markdown):\n"
                "  [N] [$sandbox] short description | Files: file1, file2 | Goal: one sentence"
            ),
        )
    except FileNotFoundError:
        return None

    try:
        result = subprocess.run(
            [
                "openclaw", "infer", "model", "run",
                "--model", lead_model,
                "--prompt", prompt,
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        import json as _json
        data = _json.loads(result.stdout)
        text = ""
        if isinstance(data, dict):
            outputs = data.get("outputs", [])
            for out in outputs:
                if isinstance(out, dict) and "text" in out:
                    text += out["text"] + "\n"
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "text" in item:
                    text += item["text"] + "\n"
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    if not text.strip():
        return None

    # Parse lines matching: [N] [sandbox] description
    _SUBTASK_RE = re.compile(r"^\s*\[(\d+)\]\s*\[([^\]]+)\]\s+(.+)$", re.MULTILINE)
    subtasks: list[dict] = []
    seen_titles: set[str] = set()

    for m in _SUBTASK_RE.finditer(text):
        title = m.group(3).strip()
        # Strip optional "| Files: ..." or "| Goal: ..." suffix from title
        if "|" in title:
            title, _, files_part = title.partition("|")
            title = title.strip()
            files = files_part.replace("Files:", "").replace("files:", "").strip()
            # Strip Goal suffix if present in files_part
            if "|" in files:
                files, _, _ = files.partition("|")
                files = files.strip()
        else:
            files = "auto-detected from analysis"

        # Deduplicate by title
        if title in seen_titles:
            continue
        seen_titles.add(title)

        subtasks.append({
            "title": f"[{sandbox}] {title}",
            "goal": title,
            "files": files,
            "model": _soldier_model,
        })

    return subtasks if subtasks else None


def _analyze_task(task, errors, sandbox, sandbox_path, soldier_model):
    """Analyze task using project structure + task description."""
    import re
    subtasks = []
    plan = _read_plan(sandbox_path)
    src_map = _get_src_map(sandbox_path)
    task_lower = task.lower()

    # Detect project type
    project_type = _detect_project_type(sandbox_path)

    # Extract file references from the task description
    referenced_files = _extract_file_refs(task, sandbox_path)

    # TypeScript errors (for any TS/TSX project)
    if errors:
        error_summary = "; ".join([e.split(": ")[1] for e in errors[:5] if ": " in e])
        subtasks.append({
            "title": f"[{sandbox}] Fix TypeScript errors ({len(errors)} found)",
            "goal": f"Fix the following TypeScript errors in {sandbox}: {error_summary}",
            "files": "auto-detected from error locations",
            "model": soldier_model,
        })

    # Task-based breakdown: use the task description as primary input
    if referenced_files:
        # Task references specific files - create focused subtask
        subtasks.append({
            "title": f"[{sandbox}] {task[:60]}",
            "goal": task,
            "files": ", ".join(referenced_files),
            "model": soldier_model,
        })
    elif "test" in task_lower and "run" in task_lower:
        # Testing task
        subtasks.append({
            "title": f"[{sandbox}] Run and fix tests",
            "goal": task,
            "files": "auto-detected from test output",
            "model": soldier_model,
        })

    # Project-type-aware additional checks
    if project_type == "flutter":
        _check_flutter(sandbox_path, subtasks, task, sandbox, soldier_model)
    elif project_type == "python":
        _check_python(sandbox_path, subtasks, task, sandbox, soldier_model)
    elif project_type == "node":
        _check_node(sandbox_path, subtasks, task, sandbox, soldier_model)

    # If no subtasks derived, pass the full task as a single subtask
    if not subtasks:
        subtasks = [{
            "title": "Execute task",
            "goal": task,
            "files": "auto-detected from analysis",
            "model": soldier_model,
        }]

    return subtasks


def _detect_project_type(sandbox_path: Path) -> str:
    """Auto-detect project type from sandbox contents."""
    if (sandbox_path / "pubspec.yaml").exists():
        return "flutter"
    if (sandbox_path / "project.godot").exists() or (sandbox_path / "godot.project").exists():
        return "godot"
    if (sandbox_path / "setup.py").exists() or (sandbox_path / "pyproject.toml").exists():
        return "python"
    if (sandbox_path / "package.json").exists():
        return "node"
    return "unknown"


def _extract_file_refs(task: str, sandbox_path: Path) -> list[str]:
    """Extract file path references from a task description."""
    import re
    refs = []
    # Match common file path patterns like lib/..., src/..., test/...
    for m in re.finditer(r'(?:^|\s)((?:lib|src|assets|test|scripts|app|config|ios|android|web)/[\w./-]+\.\w+)', task):
        path = m.group(1)
        full_path = sandbox_path / path
        if full_path.exists() or full_path.parent.exists():
            refs.append(path)
    return refs


def _check_flutter(sandbox_path: Path, subtasks: list, task: str, sandbox: str, soldier_model: str):
    """Add Flutter-specific checks and subtasks."""
    task_lower = task.lower()
    analyze_file = sandbox_path / "analysis_options.yaml"
    if analyze_file.exists() and ("analyze" in task_lower or "lint" in task_lower):
        subtasks.append({
            "title": f"[{sandbox}] Run flutter analyze and fix issues",
            "goal": f"Run 'flutter analyze' in {sandbox} and fix any reported issues.",
            "files": "auto-detected from analysis output",
            "model": soldier_model,
        })


def _check_python(sandbox_path: Path, subtasks: list, task: str, sandbox: str, soldier_model: str):
    """Add Python-specific checks and subtasks."""
    task_lower = task.lower()
    if "lint" in task_lower or "ruff" in task_lower:
        subtasks.append({
            "title": f"[{sandbox}] Run linter and fix issues",
            "goal": f"Run the project's linter in {sandbox} and fix issues.",
            "files": "auto-detected from linter output",
            "model": soldier_model,
        })


def _check_node(sandbox_path: Path, subtasks: list, task: str, sandbox: str, soldier_model: str):
    """Add Node-specific checks and subtasks."""
    task_lower = task.lower()
    if "lint" in task_lower or "format" in task_lower:
        subtasks.append({
            "title": f"[{sandbox}] Run linter and fix issues",
            "goal": f"Run the project's linter in {sandbox} and fix issues.",
            "files": "auto-detected from linter output",
            "model": soldier_model,
        })


if __name__ == "__main__":
    orchestrate()
