"""HERO Brainstorm Phase (Phase 0) — Skill Scanner & Project Brief Generator.

Matches a user task to relevant agent-skills, extracts quality gates,
and generates a project brief + constraints dict for the HERO pipeline.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SKILLS_DIR = Path.home() / ".agents" / "skills" / "agent-skills" / "skills"
BRAINSTORM_DIR = Path.home() / ".hero" / "brainstorm"

# Keyword → skill mapping
SKILL_KEYWORDS: dict[str, list[str]] = {
    "spec-driven-development": ["spec", "requirement", "define", "feature", "new project"],
    "planning-and-task-breakdown": ["plan", "breakdown", "task", "estimate", "milestone"],
    "incremental-implementation": ["build", "implement", "code", "develop", "feature"],
    "test-driven-development": ["test", "tdd", "coverage", "unittest", "spec"],
    "code-review-and-quality": ["review", "quality", "pr", "pull request", "audit"],
    "code-simplification": ["simplify", "refactor", "cleanup", "dry", "extract"],
    "security-and-hardening": ["security", "auth", "permission", "owasp", "vulnerability"],
    "performance-optimization": ["performance", "speed", "optimize", "latency", "bundle"],
    "flutter-apply-architecture-best-practices": ["flutter", "dart", "mobile app", "ui", "widget"],
    "flutter-build-responsive-layout": ["responsive", "layout", "mobile", "screen", "adaptive"],
    "flutter-setup-declarative-routing": ["routing", "navigation", "go_router", "route"],
    "flutter-use-http-package": ["http", "network", "api", "fetch", "dio"],
    "flutter-add-widget-test": ["test", "widget test", "unittest", "coverage"],
    "flutter-add-widget-preview": ["preview", "storybook", "gallery", "component"],
    "flutter-fix-layout-issues": ["layout", "overflow", "render", "flex", "box"],
    "mobile-app-debugging": ["debug", "crash", "bug", "log", "inspect", "devtools"],
    "mobile-android-design": ["android", "material", "design", "theme"],
    "api-and-interface-design": ["api", "endpoint", "rest", "graphql", "interface"],
    "frontend-ui-engineering": ["ui", "ux", "frontend", "component", "layout", "responsive"],
    "context-engineering": ["context", "prompt", "llm", "token", "engineering"],
    "source-driven-development": ["source", "git", "branch", "commit", "workflow"],
    "debugging-and-error-recovery": ["debug", "error", "exception", "crash", "trace"],
    "ci-cd-and-automation": ["ci", "cd", "pipeline", "automation", "github actions"],
    "shipping-and-launch": ["deploy", "release", "ship", "publish", "launch"],
    "documentation-and-adrs": ["docs", "readme", "adr", "changelog", "documentation"],
}


def _build_reverse_index() -> dict[str, list[str]]:
    """Build keyword → [skill names] reverse index from SKILL_KEYWORDS."""
    index: dict[str, list[str]] = {}
    for skill_name, keywords in SKILL_KEYWORDS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in index:
                index[kw_lower] = []
            index[kw_lower].append(skill_name)
    return index


def _detect_new_project(task: str, sandbox_path: Path | None) -> bool:
    """Detect if this is a new project (from scratch) vs an existing project task."""
    task_lower = task.lower()
    new_project_signals = [
        "new", "build from scratch", "create new", "start new",
        "new project", "fresh project", "standalone", "brand new",
    ]
    existing_signals = [
        "fix", "bug", "existing", "in ", "current", "in-repo",
        "in the repo", "in codebase", "in project",
    ]
    for signal in new_project_signals:
        if signal in task_lower:
            return True
    for signal in existing_signals:
        if signal in task_lower:
            return False
    # If sandbox path exists with real code, consider it existing
    if sandbox_path and sandbox_path.exists():
        src = sandbox_path / "src"
        lib = sandbox_path / "lib"
        if src.exists() or lib.exists():
            return False
    return True


def _extract_gates(skill_md: str) -> list[str]:
    """Parse a SKILL.md and extract quality gates (checklist items, rules, warnings).

    Looks for:
    - Bullet lists (- item, * item)
    - Numbered steps
    - "Never Skip" rules
    - "KEY" / "GATE" / "RULE" prefixed lines
    - Checklist-style lines with [ ], ( ), or x
    """
    gates: list[str] = []
    lines = skill_md.splitlines()

    for line in lines:
        stripped = line.strip()
        # Skip empty lines and very long lines (likely paragraphs)
        if not stripped or len(stripped) > 200:
            continue

        # Bullet list items
        m = re.match(r"^[-*•]\s+(.+)$", stripped)
        if m:
            item = m.group(1).strip()
            if item and len(item) > 4:
                gates.append(item)
            continue

        # Numbered steps
        m = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if m:
            item = m.group(1).strip()
            if item and len(item) > 4:
                gates.append(item)
            continue

        # "Never Skip" / "KEY" / "GATE" / "RULE" lines
        special_prefixes = ("never skip", "key ", "gate ", "rule ", "★", "✓ ", "[x] ", "[ ] ")
        for prefix in special_prefixes:
            if stripped.lower().startswith(prefix):
                cleaned = stripped[len(prefix):].strip()
                if cleaned and len(cleaned) > 4:
                    gates.append(cleaned)
                break

        # Checklist items [x] or [ ]
        m = re.match(r"^\[[ x\-✔✗]\]\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            item = m.group(1).strip()
            if item and len(item) > 4:
                gates.append(item)

    return gates


def _match_skills(task: str) -> list[dict[str, Any]]:
    """Match task keywords to skills, load SKILL.md for each matched skill."""
    if not SKILLS_DIR.exists():
        return []

    reverse_index = _build_reverse_index()
    task_lower = task.lower()
    matched_names: set[str] = set()
    scored: list[tuple[int, str]] = []

    for keyword, skill_names in reverse_index.items():
        if keyword in task_lower:
            for sn in skill_names:
                if sn not in matched_names:
                    matched_names.add(sn)
                    scored.append((scored.count((0, sn)), sn))

    # Sort skills by specificity: more keywords = higher score
    # Re-score
    skill_scores: dict[str, int] = {}
    for keyword, skill_names in reverse_index.items():
        if keyword in task_lower:
            for sn in skill_names:
                skill_scores[sn] = skill_scores.get(sn, 0) + 1

    sorted_skills = sorted(
        [(score, name) for name, score in skill_scores.items()],
        reverse=True
    )

    results: list[dict[str, Any]] = []
    for score, name in sorted_skills:
        skill_path = SKILLS_DIR / name / "SKILL.md"
        if not skill_path.exists():
            continue

        try:
            content = skill_path.read_text(encoding="utf-8")
        except Exception:
            continue

        gates = _extract_gates(content)

        # Extract first 200 chars as summary
        summary = content[:200].replace("\n", " ").strip()

        results.append({
            "name": name,
            "path": str(skill_path),
            "score": score,
            "gates": gates,
            "summary": summary,
        })

    return results


def _is_mechanical_task(task: str) -> bool:
    """Detect lightweight/mechanical tasks that don't need full skill scanning."""
    task_lower = task.lower()
    mechanical_signals = [
        "fix typo", "bump version", "update readme", "change comment",
        "rename variable", "reformat", "lint", "prettify", "bump dependency",
        "add import", "remove import", "format code",
    ]
    return any(signal in task_lower for signal in mechanical_signals)


def _write_brief(
    sandbox: str,
    task: str,
    matches: list[dict[str, Any]],
    is_new: bool,
    constraints: dict[str, Any],
) -> str:
    """Write a markdown brief to ~/.hero/brainstorm/<timestamp>.md"""
    BRAINSTORM_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    brief_path = BRAINSTORM_DIR / f"{sandbox}_{ts}.md"

    gate_tag = "✨Qualit" if is_new else "⚡Quality"
    project_tag = "🆕 New Project" if is_new else "🔧 Existing Project"

    lines = [
        f"# Brainstorm Brief — {sandbox}",
        f"",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Task:** {task}",
        f"**Type:** {project_tag}",
        f"",
        f"---",
        f"",
        f"## Task",
        f"",
        f"{task}",
        f"",
        f"---",
        f"",
        f"## Matched Skills ({len(matches)})",
        f"",
    ]

    if not matches:
        lines.append("*No skills matched — using basic constraints.*\n")
    else:
        for m in matches:
            lines.append(f"### [{m['score']} keywords] {m['name']}")
            lines.append(f"")
            lines.append(f"```\n{m['summary']}\n```")
            if m["gates"]:
                lines.append(f"")
                lines.append(f"**Quality Gates:**")
                for g in m["gates"][:10]:
                    lines.append(f"- {g}")
            lines.append(f"")

    lines.extend([
        f"---",
        f"",
        f"## {gate_tag} Gates",
        f"",
        f"```python",
        f"constraints = {json.dumps(constraints, indent=2)}",
        f"```",
        f"",
        f"---",
        f"",
        f"## Workflow",
        f"",
        f"1. **Define** → SPEC.md generated from spec-driven-development skill",
        f"2. **Plan** → Task breakdown from planning-and-task-breakdown",
        f"3. **Build** → Incremental implementation with TDD",
        f"4. **Verify** → Code review + debugging",
        f"5. **Ship** → CI/CD → Deploy",
    ])

    brief_path.write_text("\n".join(lines), encoding="utf-8")
    return str(brief_path)


def brainstorm_task(task: str, sandbox: str, sandbox_path: str | None = None) -> dict[str, Any]:
    """Run the Brainstorm phase.

    Args:
        task: The user's task description.
        sandbox: Sandbox name for brief naming.
        sandbox_path: Optional path to existing sandbox.

    Returns a dict with:
    - is_new_project: bool
    - matched_skills: list of {name, path, score, gates, summary}
    - brief_path: str (path to written brief file)
    - constraints: dict of quality gates to enforce
    """
    sandbox_path_obj = Path(sandbox_path) if sandbox_path else None
    is_new = _detect_new_project(task, sandbox_path_obj)
    is_mechanical = _is_mechanical_task(task)

    # Light scan for mechanical tasks
    if is_mechanical:
        constraints = {
            "analysis": True,
            "verify": True,
            "scan_depth": "minimal",
        }
        brief_path = _write_brief(sandbox, task, [], is_new, constraints)
        return {
            "is_new_project": is_new,
            "matched_skills": [],
            "brief_path": brief_path,
            "constraints": constraints,
        }

    # Full or focused skill scan
    matches = _match_skills(task)
    depth = "full" if is_new else "focused"

    # Build constraints dict from matched skills
    all_gates: list[str] = []
    for m in matches:
        all_gates.extend(m["gates"])

    constraints = {
        "analysis": True,
        "verify": True,
        "scan_depth": depth,
        "quality_gates": all_gates[:30],  # cap at 30 gates
        "skills_count": len(matches),
    }

    brief_path = _write_brief(sandbox, task, matches, is_new, constraints)

    return {
        "is_new_project": is_new,
        "matched_skills": matches,
        "brief_path": brief_path,
        "constraints": constraints,
    }


def run(sandbox: str, task: str, sandbox_path: str | None = None) -> dict[str, Any]:
    """Main entry point. Returns constraints dict for pipeline manifest."""
    result = brainstorm_task(task, sandbox, sandbox_path)
    return result["constraints"]
