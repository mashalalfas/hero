"""NAVIGATE pipeline stage.

Synthesises code-graph intelligence from **graphify** and **Understand**
into a single ``NAVIGATION_TREE.md`` living document.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from hero.graphify.client import GraphifyClient


def run_navigate(sandbox_path: Path, verbose: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Run NAVIGATION stage and return structured results.

    Parameters
    ----------
    sandbox_path : Path
        Path to the sandbox / project directory.
    verbose : bool, default=False
        Include detailed output in each check result.
    **kwargs
        Extra arguments forwarded to underlying tools.

    Returns
    -------
    dict
        Standardised result dict with ``passed``, ``score``, ``status``,
        ``checks``, and ``findings``.
    """
    path = Path(sandbox_path).resolve()
    findings: list[dict[str, str]] = []
    checks: dict[str, Any] = {}

    # ── 1. Graphify graph ──────────────────────────────────────────────
    graphify_dir = path / "graphify-out"
    manifest_path = graphify_dir / "manifest.json"
    graphify_graph_path = graphify_dir / "graph.json"

    graphify_stale = _is_graphify_stale(manifest_path, path)
    graphify_ok = graphify_graph_path.exists()

    if graphify_stale or not graphify_ok:
        checks["graphify"] = {"passed": False, "summary": "Graphify graph stale or missing — updating", "detail": ""}
        try:
            client = GraphifyClient()
            client.update(str(path))
            checks["graphify"]["passed"] = True
            checks["graphify"]["summary"] = "Graphify graph updated"
        except Exception as exc:
            checks["graphify"]["summary"] = f"Graphify update failed: {exc}"
            findings.append({"severity": "error", "check": "graphify", "message": str(exc)})
    else:
        checks["graphify"] = {"passed": True, "summary": "Graphify graph up-to-date", "detail": ""}

    # ── 2. Understand knowledge graph ──────────────────────────────────
    understand_dir = path / ".understand-anything"
    kg_path = understand_dir / "knowledge-graph.json"

    understand_stale = _is_understand_stale(kg_path, path)
    understand_ok = kg_path.exists()

    if understand_stale or not understand_ok:
        checks["understand"] = {"passed": False, "summary": "Understand KG stale or missing — rebuilding", "detail": ""}
        try:
            result = subprocess.run(
                ["hero", "map", "--path", str(path), "--no-dashboard"],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(path),
            )
            checks["understand"]["passed"] = True
            checks["understand"]["summary"] = "Understand KG rebuilt"
            if verbose:
                checks["understand"]["detail"] = result.stdout
        except subprocess.CalledProcessError as exc:
            checks["understand"]["summary"] = f"Understand map failed: {exc.stderr or exc.stdout}"
            findings.append({"severity": "error", "check": "understand", "message": exc.stderr or str(exc)})
        except FileNotFoundError:
            checks["understand"]["summary"] = "'hero' command not found in PATH"
            findings.append({"severity": "error", "check": "understand", "message": "hero CLI not available"})
    else:
        checks["understand"] = {"passed": True, "summary": "Understand KG up-to-date", "detail": ""}

    # ── 3. Synthesise NAVIGATION_TREE.md ───────────────────────────────
    nav_tree_path = path / "NAVIGATION_TREE.md"
    try:
        _synthesise_navigation_tree(path, nav_tree_path, graphify_graph_path, kg_path)
        checks["synthesis"] = {"passed": True, "summary": f"NAVIGATION_TREE.md written to {nav_tree_path}", "detail": ""}
    except Exception as exc:
        checks["synthesis"] = {"passed": False, "summary": f"Synthesis failed: {exc}", "detail": ""}
        findings.append({"severity": "error", "check": "synthesis", "message": str(exc)})

    # ── 4. Score ───────────────────────────────────────────────────────
    passed_count = sum(1 for c in checks.values() if c.get("passed"))
    total_count = len(checks)
    score = int((passed_count / total_count) * 100) if total_count else 0

    if score >= 70:
        status = "pass"
        passed = True
    elif score >= 50:
        status = "warn"
        passed = True
    else:
        status = "fail"
        passed = False

    return {
        "sandbox": str(path),
        "passed": passed,
        "score": score,
        "status": status,
        "checks": checks,
        "findings": findings,
    }


# ── Staleness helpers ──────────────────────────────────────────────────


def _is_graphify_stale(manifest_path: Path, project_root: Path) -> bool:
    """Return True if any tracked file is newer than the manifest."""
    if not manifest_path.exists():
        return True

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return True

    for fpath_str, meta in manifest.items():
        fpath = Path(fpath_str)
        if not fpath.exists():
            # File was deleted — graph is stale
            return True
        stored_mtime = meta.get("mtime", 0)
        current_mtime = fpath.stat().st_mtime
        if abs(current_mtime - stored_mtime) > 0.5:
            return True

    # Also check for *new* files not in manifest
    for fpath in _iter_source_files(project_root):
        if str(fpath) not in manifest:
            return True

    return False


def _is_understand_stale(kg_path: Path, project_root: Path) -> bool:
    """Return True if any source file is newer than the knowledge graph."""
    if not kg_path.exists():
        return True

    kg_mtime = kg_path.stat().st_mtime

    for fpath in _iter_source_files(project_root):
        try:
            if fpath.stat().st_mtime > kg_mtime:
                return True
        except OSError:
            continue

    return False


def _iter_source_files(project_root: Path) -> Any:
    """Yield source-code files under *project_root*, skipping common noise."""
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        ".tox", ".pytest_cache", ".mypy_cache", "dist", "build",
        ".understand-anything", "graphify-out", ".idea", ".vscode",
    }
    exts = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".c", ".cpp", ".h", ".hpp", ".swift", ".kt", ".scala",
        ".rb", ".php", ".cs", ".fs", ".dart", ".lua",
    }

    for root, dirs, files in os.walk(project_root):
        # Prune skip_dirs in-place
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for fname in files:
            if fname.endswith(tuple(exts)):
                yield Path(root) / fname


# ── Synthesis helpers ──────────────────────────────────────────────────


def _synthesise_navigation_tree(
    project_root: Path,
    output_path: Path,
    graphify_path: Path,
    understand_path: Path,
) -> None:
    """Read both graphs and write a unified NAVIGATION_TREE.md."""
    graphify_data = _load_json(graphify_path)
    understand_data = _load_json(understand_path)

    lines: list[str] = [
        f"# Navigation Tree — {project_root.name}",
        "",
        "Auto-generated by HERO NAVIGATE stage. **Do not edit manually.**",
        "",
        "## Overview",
        "",
    ]

    # Graphify summary
    g_nodes = _safe_len(graphify_data, "nodes")
    g_edges = _safe_len(graphify_data, "links") or _safe_len(graphify_data, "edges")
    g_communities = len({n.get("community") for n in graphify_data.get("nodes", []) if n.get("community") is not None})

    lines.extend([
        f"- **Graphify**: {g_nodes} nodes · {g_edges} edges · {g_communities} communities",
    ])

    # Understand summary
    u_nodes = _safe_len(understand_data, "nodes")
    u_edges = _safe_len(understand_data, "links") or _safe_len(understand_data, "edges")
    u_layers = len({n.get("layer") for n in understand_data.get("nodes", []) if n.get("layer") is not None})

    lines.extend([
        f"- **Understand**: {u_nodes} nodes · {u_edges} edges · {u_layers} layers",
        "",
    ])

    # Graphify community tree
    lines.extend([
        "## Graphify Communities",
        "",
    ])
    lines.extend(_render_graphify_tree(graphify_data))

    # Understand layer tree
    lines.extend([
        "",
        "## Understand Layers",
        "",
    ])
    lines.extend(_render_understand_tree(understand_data))

    # File index
    lines.extend([
        "",
        "## File Index",
        "",
    ])
    lines.extend(_render_file_index(graphify_data, understand_data))

    output_path.write_text("\n".join(lines) + "\n")


def _load_json(path: Path) -> dict[str, Any]:
    """Safely load JSON; return empty dict on failure."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def _safe_len(data: dict[str, Any], key: str) -> int:
    """Return len of *data[key]* if it is a list, else 0."""
    val = data.get(key)
    return len(val) if isinstance(val, list) else 0


def _render_graphify_tree(data: dict[str, Any]) -> list[str]:
    """Render community hierarchy from graphify graph."""
    nodes = data.get("nodes", [])
    if not nodes:
        return ["_No graphify data available._", ""]

    # Group by community
    communities: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        comm = n.get("community", 0)
        communities.setdefault(comm, []).append(n)

    lines: list[str] = []
    for comm_id in sorted(communities):
        members = communities[comm_id]
        hub = _pick_hub(members)
        lines.append(f"- **Community {comm_id}** — hub: `{hub}`")
        for m in members[:5]:
            label = m.get("label", "unknown")
            if label == hub:
                continue
            lines.append(f"  - `{label}`")
        if len(members) > 5:
            lines.append(f"  - _… and {len(members) - 5} more_")
        lines.append("")

    return lines


def _render_understand_tree(data: dict[str, Any]) -> list[str]:
    """Render layer hierarchy from Understand knowledge graph."""
    nodes = data.get("nodes", [])
    if not nodes:
        return ["_No Understand data available._", ""]

    # Group by layer
    layers: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        layer = n.get("layer", "unknown")
        layers.setdefault(layer, []).append(n)

    lines: list[str] = []
    for layer_name in sorted(layers):
        members = layers[layer_name]
        lines.append(f"- **{layer_name}** ({len(members)} nodes)")
        for m in members[:5]:
            label = m.get("label", m.get("id", "unknown"))
            lines.append(f"  - `{label}`")
        if len(members) > 5:
            lines.append(f"  - _… and {len(members) - 5} more_")
        lines.append("")

    return lines


def _render_file_index(
    graphify_data: dict[str, Any],
    understand_data: dict[str, Any],
) -> list[str]:
    """Render a deduplicated list of source files referenced in both graphs."""
    files: set[str] = set()

    for n in graphify_data.get("nodes", []):
        sf = n.get("source_file")
        if sf:
            files.add(sf)

    for n in understand_data.get("nodes", []):
        sf = n.get("source_file") or n.get("file")
        if sf:
            files.add(sf)

    if not files:
        return ["_No source files indexed._", ""]

    lines: list[str] = []
    for f in sorted(files):
        lines.append(f"- `{f}`")
    return lines


def _pick_hub(members: list[dict[str, Any]]) -> str:
    """Heuristic: pick the node with the most connections as community hub."""
    if not members:
        return "unknown"
    # Simple heuristic: shortest non-file label
    candidates = [m for m in members if m.get("file_type") != "file"]
    if not candidates:
        candidates = members
    best = min(candidates, key=lambda m: len(m.get("label", "")))
    return best.get("label", "unknown")
