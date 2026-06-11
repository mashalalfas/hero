"""hero map — Run Understand Anything knowledge-graph generation and launch the dashboard.

Wraps the full understand-anything pipeline: scan, extract, batch, structure,
merge, and finalize into a knowledge graph, then serves it via the interactive
Vite dashboard.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import click

from hero.logging import get_logger
from hero.state.index import IndexState

SANDBOX_DIR = Path.home() / ".hero" / "sandboxes"
HERO_HOME = Path.home() / ".hero"
UNDERSTAND_SKILL_DIR = (
    Path.home() / ".openclaw" / "skills" / "understand-anything" / "understand"
)
UNDERSTAND_PLUGIN_DIR = Path.home() / ".understand-anything-plugin"

_logger = get_logger("map")


# ── Plugin root resolution ──────────────────────────────────────────────


def _resolve_plugin_root() -> Path | None:
    """Resolve the understand-anything plugin root directory.

    Checks common install locations in priority order.  Mirrors the
    resolution logic in the understand SKILL.md and understand-dashboard
    SKILL.md so the same candidate list is covered.
    """
    # 1. Environment variable override
    env_root = os.environ.get("UNDERSTAND_PLUGIN_ROOT")
    if env_root:
        p = Path(env_root)
        if _is_valid_plugin_root(p):
            return p.resolve()

    # 2. Universal symlink path (most common install)
    p = UNDERSTAND_PLUGIN_DIR
    if _is_valid_plugin_root(p):
        return p.resolve()

    # 3. Skill symlink: skills/understand/ -> two dirs up to plugin root
    try:
        skill_real = os.path.realpath(str(UNDERSTAND_SKILL_DIR))
        two_up = Path(skill_real).parent.parent
        if _is_valid_plugin_root(two_up):
            return two_up.resolve()
    except OSError:
        pass

    # 4. Alternative clone paths
    for candidate in (
        Path.home() / ".codex" / "understand-anything" / "understand-anything-plugin",
        Path.home() / ".opencode" / "understand-anything" / "understand-anything-plugin",
        Path.home() / ".pi" / "understand-anything" / "understand-anything-plugin",
        Path.home() / "understand-anything" / "understand-anything-plugin",
    ):
        if _is_valid_plugin_root(candidate):
            return candidate.resolve()

    return None


def _is_valid_plugin_root(p: Path) -> bool:
    """Return True if *p* looks like the understand-anything plugin checkout."""
    return (
        p.exists()
        and (p / "package.json").is_file()
        and (p / "pnpm-workspace.yaml").is_file()
    )


# ── Sandbox / path resolution ───────────────────────────────────────────


def _resolve_sandbox_path(sandbox: str | None, path: str | None) -> Path:
    """Resolve the project root directory from sandbox name or direct path.

    At least one of *sandbox* or *path* must be provided.
    """
    if path:
        p = Path(path).resolve()
        if not p.is_dir():
            raise click.ClickException(f"Path is not a directory: {p}")
        return p

    if sandbox:
        index = IndexState()
        entry = index.get_sandbox(sandbox)
        if not entry:
            raise click.ClickException(
                f"Sandbox '{sandbox}' not found. Run 'hero scan' first."
            )
        return Path(entry["path"]).resolve()

    raise click.ClickException("Specify --sandbox <name> or --path <path>")


# ── Prerequisites ───────────────────────────────────────────────────────


def _check_nodejs() -> None:
    """Verify Node.js >= 22 and pnpm are available."""
    try:
        r = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            raise click.ClickException(
                "Node.js is not installed or not in PATH."
            )
        ver = r.stdout.strip().lstrip("v")
        major = int(ver.split(".")[0])
        if major < 22:
            raise click.ClickException(
                f"Node.js >= 22 required, found {ver}. "
                "Install a newer version."
            )
    except FileNotFoundError:
        raise click.ClickException(
            "Node.js is not installed. Install Node.js >= 22 and pnpm >= 10."
        )

    try:
        r = subprocess.run(
            ["pnpm", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            raise click.ClickException(
                "pnpm is not installed or not in PATH."
            )
    except FileNotFoundError:
        raise click.ClickException(
            "pnpm is not installed. Install pnpm >= 10."
        )


def _check_understand_installed() -> Path:
    """Check that Understand Anything is installed and return plugin root."""
    plugin_root = _resolve_plugin_root()
    if not plugin_root:
        raise click.ClickException(
            "Cannot find the understand-anything plugin.\n"
            "Checked:\n"
            f"  - $UNDERSTAND_PLUGIN_ROOT\n"
            f"  - {UNDERSTAND_PLUGIN_DIR}\n"
            f"  - Symlink from {UNDERSTAND_SKILL_DIR}\n"
            "\n"
            "Install it by following the instructions at:\n"
            "  https://github.com/understand-anything/understand-anything-plugin"
        )
    return plugin_root


def _ensure_pnpm_built(plugin_root: Path) -> None:
    """Ensure core package and all workspace dependencies are built.

    Checks for ``packages/core/dist/index.js`` as proof of build.
    """
    core_dist = plugin_root / "packages" / "core" / "dist" / "index.js"
    if core_dist.exists():
        return

    click.echo("  Building understand-anything dependencies...")
    _logger.info(
        "building understand-anything dependencies",
        plugin_root=str(plugin_root),
    )

    r = subprocess.run(
        ["pnpm", "install"],
        cwd=str(plugin_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        raise click.ClickException(
            f"pnpm install failed:\n{r.stderr[:500]}"
        )

    r = subprocess.run(
        ["pnpm", "--filter", "@understand-anything/core", "build"],
        cwd=str(plugin_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        raise click.ClickException(
            f"Core build failed:\n{r.stderr[:500]}"
        )

    click.echo("  Build complete.")


# ── Subprocess runner ───────────────────────────────────────────────────


def _run_phase(
    phase_label: str,
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run a pipeline phase command with consistent error handling.

    Returns the ``CompletedProcess`` on success, raises ``ClickException``
    on failure.
    """
    _logger.info(
        f"phase: {phase_label}",
        cmd=" ".join(cmd),
        cwd=str(cwd or os.getcwd()),
    )
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Relay warnings from script stderr
        if r.stderr:
            for line in r.stderr.strip().split("\n"):
                stripped = line.strip()
                if stripped.startswith("Warning:") or stripped.startswith(
                    "Error:"
                ):
                    _logger.warning(stripped)
        if r.returncode != 0:
            raise click.ClickException(
                f"{phase_label} failed (exit {r.returncode}):\n"
                f"{r.stderr[:600]}"
            )
        return r
    except subprocess.TimeoutExpired:
        raise click.ClickException(
            f"{phase_label} timed out after {timeout}s"
        )


# ── Batch conversion helper ────────────────────────────────────────────


def _convert_batch_to_graph(
    project_root: str,
    raw_path: Path,
    output_path: Path,
    scan_files: list[dict],
) -> None:
    """Convert extract-structure.mjs output (per-file results) to graph
    nodes/edges format expected by merge-batch-graphs.py.
    """
    if not raw_path.exists():
        click.echo(f"  Warning: batch raw results not found: {raw_path}", err=True)
        # Write an empty batch so the merge script doesn't choke
        output_path.write_text(json.dumps({"nodes": [], "edges": []}))
        return

    try:
        raw = json.loads(raw_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"  Warning: cannot read batch raw results: {exc}", err=True)
        output_path.write_text(json.dumps({"nodes": [], "edges": []}))
        return

    results = raw.get("results", [])
    if not results:
        output_path.write_text(json.dumps({"nodes": [], "edges": []}))
        return

    nodes = []
    edges = []
    seen_ids = set()

    for r in results:
        path = r.get("path", "")
        lang = r.get("language", "unknown")
        cat = r.get("fileCategory", "code")

        # Map category to node type
        ntype: str = {
            "docs": "document",
            "config": "config",
            "infra": "service",
            "data": "file",
            "script": "file",
            "markup": "file",
        }.get(cat, "file")

        node_id = f"{ntype}:{path}"

        summary = r.get("summary", "") or f"{ntype.capitalize()}: {path.rsplit('/', 1)[-1]}"
        tags = [lang, cat]

        file_node = {
            "id": node_id,
            "type": ntype,
            "name": path.rsplit("/", 1)[-1],
            "filePath": path,
            "summary": summary,
            "tags": tags,
            "complexity": r.get("metrics", {}).get("complexity", "moderate"),
        }
        nodes.append(file_node)
        seen_ids.add(node_id)

        # Functions
        for func in r.get("functions", []):
            fname = func.get("name", "unknown")
            fid = f"function:{path}:{fname}"
            if fid in seen_ids:
                continue
            func_node = {
                "id": fid,
                "type": "function",
                "name": fname,
                "filePath": path,
                "summary": func.get("comment", "") or f"Function {fname}",
                "tags": [lang],
                "complexity": func.get("complexity", "moderate"),
            }
            nodes.append(func_node)
            seen_ids.add(fid)
            edges.append({
                "source": node_id, "target": fid,
                "type": "contains", "weight": 1.0,
            })

        # Classes
        for cls in r.get("classes", []):
            cname = cls.get("name", "unknown")
            cid = f"class:{path}:{cname}"
            if cid in seen_ids:
                continue
            cls_node = {
                "id": cid,
                "type": "class",
                "name": cname,
                "filePath": path,
                "summary": cls.get("comment", "") or f"Class {cname}",
                "tags": [lang],
                "complexity": "moderate",
            }
            nodes.append(cls_node)
            seen_ids.add(cid)
            edges.append({
                "source": node_id, "target": cid,
                "type": "contains", "weight": 1.0,
            })

        # Sections (for docs/configs)
        for sec in r.get("sections", []):
            sname = sec.get("name", "section")
            sid = f"function:{path}:{sname}"
            if sid in seen_ids:
                continue
            sec_node = {
                "id": sid,
                "type": "function",
                "name": sname,
                "filePath": path,
                "summary": sec.get("comment", "") or f"Section: {sname}",
                "tags": [lang, "section"],
                "complexity": "simple",
            }
            nodes.append(sec_node)
            seen_ids.add(sid)

    # Write converted batch
    output_path.write_text(
        json.dumps({"nodes": nodes, "edges": edges}, indent=2)
    )

    click.echo(
        f"    batch {raw_path.stem.replace('batch-raw-', '')}: "
        f"{len(nodes)} nodes, {len(edges)} edges"
    )


# ── Pipeline orchestration ──────────────────────────────────────────────


def _run_pipeline(
    project_root: Path,
    plugin_root: Path,
    skill_dir: Path,
) -> dict[str, Any]:
    """Run the full Understand Anything knowledge-graph pipeline.

    Returns a dict with the final ``graph_path`` and metadata.
    """
    project_root_str = str(project_root)
    skill_dir_str = str(skill_dir)
    understand_dir = project_root / ".understand-anything"
    intermediate_dir = understand_dir / "intermediate"
    tmp_dir = understand_dir / "tmp"

    # ── Phase 0 – prepare directories ────────────────────────────────
    click.echo("\n[Phase 0/7] Preparing project directories...")
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Git commit hash
    git_hash = "unknown"
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root_str,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            git_hash = r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Purge old trash dirs (> 7 days)
    for trash in understand_dir.glob(".trash-*"):
        try:
            age = time.time() - trash.stat().st_mtime
            if age > 7 * 86400:
                subprocess.run(
                    ["rm", "-rf", str(trash)],
                    capture_output=True,
                    timeout=30,
                )
        except OSError:
            pass

    # ── Phase 1 – scan project ───────────────────────────────────────
    click.echo("[Phase 1/7] Scanning project files...")
    scan_result = intermediate_dir / "scan-result.json"
    _run_phase(
        "Scan project",
        [
            "node",
            str(skill_dir / "scan-project.mjs"),
            project_root_str,
            str(scan_result),
        ],
        timeout=300,
    )
    click.echo(f"  Scan complete: {scan_result}")

    # Read scan data — we will inject importMap later
    scan_data = json.loads(scan_result.read_text())

    # ── Phase 1 – extract import map ─────────────────────────────────
    click.echo("[Phase 1/7] Extracting import map...")
    import_map_input = intermediate_dir / "import-map-input.json"
    import_map_input.write_text(
        json.dumps(
            {
                "projectRoot": project_root_str,
                "files": scan_data.get("files", []),
            }
        )
    )
    import_map_output = intermediate_dir / "import-map.json"
    _run_phase(
        "Extract import map",
        [
            "node",
            str(skill_dir / "extract-import-map.mjs"),
            str(import_map_input),
            str(import_map_output),
        ],
        timeout=600,
    )
    import_map_data = json.loads(import_map_output.read_text())

    # Inject ``importMap`` into scan-result.json (batches script reads it)
    scan_data["importMap"] = import_map_data.get("importMap", {})
    scan_result.write_text(json.dumps(scan_data, indent=2))

    stats = import_map_data.get("stats", {})
    click.echo(
        f"  Import map complete: {stats.get('filesScanned', 0)} files, "
        f"{stats.get('totalEdges', 0)} edges"
    )

    # ── Phase 1.5 – compute batches ──────────────────────────────────
    click.echo("[Phase 1.5/7] Computing semantic batches...")
    _run_phase(
        "Compute batches",
        ["node", str(skill_dir / "compute-batches.mjs"), project_root_str],
        timeout=300,
    )
    batches_file = intermediate_dir / "batches.json"
    batches_data = json.loads(batches_file.read_text())
    total_batches = batches_data.get("totalBatches", 0)
    click.echo(f"  Created {total_batches} batches.")

    # ── Phase 2 – extract structure per batch ────────────────────────
    click.echo(f"[Phase 2/7] Analyzing files ({total_batches} batches)...")
    for batch in batches_data.get("batches", []):
        batch_idx = batch["batchIndex"]
        batch_input = tmp_dir / f"batch-input-{batch_idx}.json"
        batch_tmp_output = tmp_dir / f"batch-raw-{batch_idx}.json"
        batch_output = intermediate_dir / f"batch-{batch_idx}.json"

        batch_input.write_text(
            json.dumps(
                {
                    "projectRoot": project_root_str,
                    "batchFiles": batch["files"],
                    "batchImportData": batch.get("batchImportData", {}),
                }
            )
        )

        click.echo(f"  Analyzing batch {batch_idx}/{total_batches}...")
        _run_phase(
            f"Extract structure batch {batch_idx}",
            [
                "node",
                str(skill_dir / "extract-structure.mjs"),
                str(batch_input),
                str(batch_tmp_output),
            ],
            timeout=600,
        )

        # Convert extraction results (per-file results format) to graph
        # nodes/edges format expected by merge-batch-graphs.py
        _convert_batch_to_graph(
            project_root_str,
            batch_tmp_output,
            batch_output,
            scan_data.get("files", []),
        )

    # ── Phase 2 – merge batch graphs ─────────────────────────────────
    click.echo("[Phase 2/7] Merging batch results...")
    _run_phase(
        "Merge batch graphs",
        [
            "python3",
            str(skill_dir / "merge-batch-graphs.py"),
            project_root_str,
        ],
        timeout=120,
    )
    assembled_graph = intermediate_dir / "assembled-graph.json"
    if not assembled_graph.exists():
        raise click.ClickException(
            "Merge script did not produce assembled-graph.json"
        )
    click.echo("  Merge complete.")

    # ── Phases 3-5 – build layers + tour ─────────────────────────────
    click.echo("[Phases 3-5/7] Building layers and guided tour...")
    _run_build_layers_and_tour(
        project_root, intermediate_dir, assembled_graph, scan_data
    )

    # ── Phase 6 – validate ───────────────────────────────────────────
    click.echo("[Phase 6/7] Validating knowledge graph...")
    _run_validate(project_root, understand_dir, intermediate_dir)

    # ── Phase 7 – save ───────────────────────────────────────────────
    click.echo("[Phase 7/7] Saving knowledge graph...")

    assembled = json.loads(assembled_graph.read_text())

    layers = _load_json_array(
        intermediate_dir / "layers.json", "layers"
    )
    tour = _load_json_array(intermediate_dir / "tour.json", "steps")

    knowledge_graph = {
        "version": "1.0.0",
        "project": {
            "name": (
                scan_data.get("projectName")
                or scan_data.get("project", {}).get("name")
                or project_root.name
            ),
            "languages": list(
                scan_data.get("stats", {})
                .get("byLanguage", {})
                .keys()
            ),
            "frameworks": scan_data.get("frameworks", []),
            "description": (
                scan_data.get("projectDescription")
                or scan_data.get("project", {}).get("description", "")
            ),
            "analyzedAt": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "gitCommitHash": git_hash,
        },
        "nodes": assembled.get("nodes", []),
        "edges": assembled.get("edges", []),
        "layers": layers,
        "tour": tour,
    }

    kg_path = understand_dir / "knowledge-graph.json"
    kg_path.write_text(json.dumps(knowledge_graph, indent=2))
    click.echo(f"  Knowledge graph written to {kg_path}")

    # ── Phase 7 – fingerprints baseline ──────────────────────────────
    click.echo("[Phase 7/7] Building fingerprints baseline...")
    fp_input_file = intermediate_dir / "fingerprint-input.json"
    source_paths = [
        f["path"]
        for f in scan_data.get("files", [])
        if f.get("fileCategory") == "code"
    ]
    fp_input_file.write_text(
        json.dumps(
            {
                "projectRoot": project_root_str,
                "sourceFilePaths": source_paths,
                "gitCommitHash": git_hash,
            }
        )
    )
    fp_ok = True
    try:
        _run_phase(
            "Build fingerprints",
            [
                "node",
                str(skill_dir / "build-fingerprints.mjs"),
                str(fp_input_file),
            ],
            timeout=300,
        )
        click.echo("  Fingerprints baseline built.")
    except click.ClickException as e:
        click.echo(f"  Warning: fingerprints skipped — {e}", err=True)
        fp_ok = False

    # ── Phase 7 – write meta.json (only after fingerprints succeeded) ─
    if fp_ok:
        meta = {
            "lastAnalyzedAt": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "gitCommitHash": git_hash,
            "version": "1.0.0",
            "analyzedFiles": len(scan_data.get("files", [])),
        }
        (understand_dir / "meta.json").write_text(
            json.dumps(meta, indent=2)
        )
        click.echo("  Metadata written to meta.json")

    # ── Phase 7 – clean up intermediate files ──────────────────────
    _cleanup_intermediates(understand_dir, intermediate_dir, tmp_dir)

    # ── Summary ──────────────────────────────────────────────────────
    _print_summary(knowledge_graph, scan_data)

    return {"graph_path": str(kg_path)}


def _load_json_array(path: Path, key: str) -> list[Any]:
    """Load a JSON file that is either a plain array or an object with *key*."""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and key in raw and isinstance(raw[key], list):
        return raw[key]
    return []


# ── Phase 3-5: layers + tour (rule-based fallback) ─────────────────────


def _run_build_layers_and_tour(
    project_root: Path,
    intermediate_dir: Path,
    assembled_graph: Path,
    scan_data: dict[str, Any],
) -> None:
    """Build architectural layers and a guided tour.

    Uses a simple rule-based approach: groups nodes by file category and
    top-level directory, then creates a basic tour from the entry point.
    This avoids needing LLM subagent dispatches for the architecture/tour
    phases.
    """
    assembled = json.loads(assembled_graph.read_text())
    nodes = assembled.get("nodes", [])

    # ── Category-to-layer map ─────────────────────────────────────────
    category_layers: dict[str, dict[str, Any]] = {
        "config": {
            "id": "layer:configuration",
            "name": "Configuration",
            "description": (
                "Configuration files (JSON, YAML, TOML, env)."
            ),
        },
        "docs": {
            "id": "layer:documentation",
            "name": "Documentation",
            "description": "Documentation files (Markdown, RST, TXT).",
        },
        "infra": {
            "id": "layer:infrastructure",
            "name": "Infrastructure",
            "description": (
                "Infrastructure and deployment files "
                "(Docker, CI/CD, K8s)."
            ),
        },
        "data": {
            "id": "layer:data",
            "name": "Data & Schema",
            "description": (
                "Data files, SQL migrations, schema definitions."
            ),
        },
        "script": {
            "id": "layer:scripts",
            "name": "Scripts",
            "description": "Build and utility scripts.",
        },
        "markup": {
            "id": "layer:frontend",
            "name": "Frontend",
            "description": (
                "Frontend markup and styles (HTML, CSS)."
            ),
        },
    }

    code_dirs: dict[str, dict[str, Any]] = {}

    for node in nodes:
        nid: str = node.get("id", "")
        ntype: str = node.get("type", "")
        file_path: str = node.get("filePath", "")

        # Non-code categories
        if ntype in ("config",):
            _layer_add_node(category_layers, "config", nid)
        elif ntype in ("document",):
            _layer_add_node(category_layers, "docs", nid)
        elif ntype in ("service", "pipeline", "resource", "endpoint"):
            _layer_add_node(category_layers, "infra", nid)
        elif ntype in ("table", "schema"):
            _layer_add_node(category_layers, "data", nid)
        elif ntype in ("file", "function", "class", "module", "concept"):
            # Group code files by their top-level directory
            if file_path:
                parts = file_path.split("/")
                top_dir = parts[0] if len(parts) > 1 else "root"
                layer_id = f"layer:{top_dir}"
                if top_dir not in code_dirs:
                    code_dirs[top_dir] = {
                        "id": layer_id,
                        "name": top_dir.replace("-", " ").title(),
                        "description": f"Source code in {top_dir}/.",
                        "nodeIds": [],
                    }
                code_dirs[top_dir]["nodeIds"].append(nid)

    layers_list: list[dict[str, Any]] = [
        v for v in category_layers.values() if v.get("nodeIds")
    ] + list(code_dirs.values())

    (intermediate_dir / "layers.json").write_text(
        json.dumps({"layers": layers_list}, indent=2)
    )

    # ── Build a basic tour ───────────────────────────────────────────
    tour_steps: list[dict[str, Any]] = []

    # Step 1: README if present
    for node in nodes:
        fp = (node.get("filePath") or "").lower()
        if fp.startswith("readme"):
            tour_steps.append(
                {
                    "order": 1,
                    "title": "Project Overview",
                    "description": (
                        "Start with the README to understand the "
                        "project's purpose and architecture."
                    ),
                    "nodeIds": [node["id"]],
                }
            )
            break

    # Step 2: Entry point
    entry_patterns = (
        "src/main.ts",
        "src/main.tsx",
        "src/index.ts",
        "src/App.tsx",
        "main.py",
        "app.py",
        "manage.py",
        "index.js",
        "main.go",
        "src/main.rs",
        "src/lib.rs",
        "Program.cs",
        "config.ru",
    )
    for node in nodes:
        fp = node.get("filePath", "")
        if any(fp.endswith(p) for p in entry_patterns):
            tour_steps.append(
                {
                    "order": 2,
                    "title": "Application Entry Point",
                    "description": (
                        f"This is where the application starts — "
                        f"{node.get('name', node.get('id', fp))}."
                    ),
                    "nodeIds": [node["id"]],
                }
            )
            break

    # Steps 3+: one per code layer (first 5 files as representative)
    for i, cd in enumerate(code_dirs.values(), start=3):
        layer_ids = cd.get("nodeIds", [])
        if not layer_ids:
            continue
        tour_steps.append(
            {
                "order": i,
                "title": cd["name"],
                "description": cd["description"],
                "nodeIds": layer_ids[:5],
            }
        )

    (intermediate_dir / "tour.json").write_text(
        json.dumps({"steps": tour_steps}, indent=2)
    )

    click.echo(
        f"  Created {len(layers_list)} layers and "
        f"{len(tour_steps)} tour steps."
    )


def _layer_add_node(
    layers: dict[str, dict[str, Any]],
    cat: str,
    node_id: str,
) -> None:
    """Append *node_id* to the category's ``nodeIds`` list."""
    if cat not in layers:
        return
    if "nodeIds" not in layers[cat]:
        layers[cat]["nodeIds"] = []
    layers[cat]["nodeIds"].append(node_id)


# ── Phase 6: validation ────────────────────────────────────────────────


def _run_validate(
    project_root: Path,
    understand_dir: Path,
    intermediate_dir: Path,
) -> None:
    """Run inline Node.js validation of the assembled graph."""
    assembled = intermediate_dir / "assembled-graph.json"
    if not assembled.exists():
        return

    validation_script = (
        understand_dir / "tmp" / "ua-inline-validate.cjs"
    )
    validation_script.parent.mkdir(parents=True, exist_ok=True)
    validation_script.write_text(
        _INLINE_VALIDATE_SCRIPT
    )

    review_output = intermediate_dir / "review.json"
    try:
        r = subprocess.run(
            ["node", str(validation_script), str(assembled), str(review_output)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            click.echo(
                f"  Warning: validation script error: {r.stderr.strip()}"
            )
            return
    except subprocess.TimeoutExpired:
        click.echo("  Warning: validation timed out")
        return
    except FileNotFoundError:
        click.echo("  Warning: node not available for validation")
        return

    try:
        review = json.loads(review_output.read_text())
    except (json.JSONDecodeError, OSError):
        click.echo("  Warning: could not read validation results")
        return

    issues = review.get("issues", [])
    warnings = review.get("warnings", [])
    stats = review.get("stats", {})

    if issues:
        click.echo(f"  Validation found {len(issues)} issue(s):")
        for iss in issues[:10]:
            click.echo(f"    - {iss}")
        if len(issues) > 10:
            click.echo(f"    ... and {len(issues) - 10} more")
    if warnings:
        for w in warnings[:5]:
            click.echo(f"    ⚠ {w}")

    click.echo(
        f"  Graph stats: {stats.get('totalNodes', 0)} nodes, "
        f"{stats.get('totalEdges', 0)} edges"
    )
    click.echo("  Validation complete.")


_INLINE_VALIDATE_SCRIPT = r"""#!/usr/bin/env node
const fs = require("fs");
const graphPath = process.argv[2];
const outputPath = process.argv[3];
try {
  const graph = JSON.parse(fs.readFileSync(graphPath, "utf8"));
  const issues = [], warnings = [];
  if (!Array.isArray(graph.nodes)) { issues.push("graph.nodes is missing or not an array"); graph.nodes = []; }
  if (!Array.isArray(graph.edges)) { issues.push("graph.edges is missing or not an array"); graph.edges = []; }
  const nodeIds = new Set();
  const seen = new Map();
  graph.nodes.forEach((n, i) => {
    if (!n.id) { issues.push("Node[" + i + "] missing id"); return; }
    if (!n.type) issues.push("Node[" + i + " '" + n.id + "'] missing type");
    if (!n.name) issues.push("Node[" + i + " '" + n.id + "'] missing name");
    if (!n.summary) issues.push("Node[" + i + " '" + n.id + "'] missing summary");
    if (seen.has(n.id)) issues.push("Duplicate node ID '" + n.id + "' at indices " + seen.get(n.id) + " and " + i);
    else seen.set(n.id, i);
    nodeIds.add(n.id);
  });
  graph.edges.forEach((e, i) => {
    if (!nodeIds.has(e.source)) issues.push("Edge[" + i + "] source '" + e.source + "' not found");
    if (!nodeIds.has(e.target)) issues.push("Edge[" + i + "] target '" + e.target + "' not found");
  });
  const fileLevelTypes = new Set(["file","config","document","service","pipeline","table","schema","resource","endpoint"]);
  const fileNodes = graph.nodes.filter(n => fileLevelTypes.has(n.type)).map(n => n.id);
  const assigned = new Map();
  if (!Array.isArray(graph.layers)) { if (graph.layers) warnings.push("graph.layers is not an array"); graph.layers = []; }
  if (!Array.isArray(graph.tour)) { if (graph.tour) warnings.push("graph.tour is not an array"); graph.tour = []; }
  graph.layers.forEach(layer => {
    (layer.nodeIds || []).forEach(id => {
      if (!nodeIds.has(id)) issues.push("Layer '" + layer.id + "' refs missing node '" + id + "'");
      if (assigned.has(id)) issues.push("Node '" + id + "' appears in multiple layers");
      assigned.set(id, layer.id);
    });
  });
  fileNodes.forEach(id => {
    if (!assigned.has(id)) issues.push("File node '" + id + "' not in any layer");
  });
  graph.tour.forEach((step, i) => {
    (step.nodeIds || []).forEach(id => {
      if (!nodeIds.has(id)) issues.push("Tour step[" + i + "] refs missing node '" + id + "'");
    });
  });
  const stats = {
    totalNodes: graph.nodes.length,
    totalEdges: graph.edges.length,
    totalLayers: graph.layers.length,
    tourSteps: graph.tour.length,
    nodeTypes: graph.nodes.reduce(function(a, n) { a[n.type] = (a[n.type]||0)+1; return a; }, {}),
    edgeTypes: graph.edges.reduce(function(a, e) { a[e.type] = (a[e.type]||0)+1; return a; }, {}),
  };
  fs.writeFileSync(outputPath, JSON.stringify({ issues, warnings, stats }, null, 2));
  process.exit(0);
} catch (err) { process.stderr.write(err.message + "\n"); process.exit(1); }
"""


# ── Cleanup ─────────────────────────────────────────────────────────────


def _cleanup_intermediates(
    understand_dir: Path,
    intermediate_dir: Path,
    tmp_dir: Path,
) -> None:
    """Move intermediate files into a timestamped trash dir (not rm)."""
    trash_dir = understand_dir / f".trash-{int(time.time())}"
    trash_dir.mkdir(parents=True, exist_ok=True)

    if intermediate_dir.exists():
        for item in intermediate_dir.iterdir():
            if item.name == "scan-result.json":
                continue  # preserve for incremental runs
            dest = trash_dir / item.name
            try:
                item.rename(dest)
            except OSError:
                subprocess.run(
                    ["mv", str(item), str(dest)],
                    capture_output=True,
                    timeout=10,
                )

    if tmp_dir.exists():
        dest = trash_dir / "tmp"
        try:
            tmp_dir.rename(dest)
        except OSError:
            subprocess.run(
                ["mv", str(tmp_dir), str(dest)],
                capture_output=True,
                timeout=10,
            )


# ── Summary ─────────────────────────────────────────────────────────────


def _print_summary(
    knowledge_graph: dict[str, Any],
    scan_data: dict[str, Any],
) -> None:
    """Print a human-readable summary of the generated knowledge graph."""
    files = scan_data.get("files", [])
    nodes = knowledge_graph.get("nodes", [])
    edges = knowledge_graph.get("edges", [])
    layers = knowledge_graph.get("layers", [])
    tour = knowledge_graph.get("tour", [])
    proj = knowledge_graph.get("project", {})

    # Category breakdown
    by_category: dict[str, int] = {}
    for f in files:
        cat = f.get("fileCategory", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    # Node type breakdown
    by_node_type: dict[str, int] = {}
    for n in nodes:
        nt = n.get("type", "unknown")
        by_node_type[nt] = by_node_type.get(nt, 0) + 1

    # Edge type breakdown
    by_edge_type: dict[str, int] = {}
    for e in edges:
        et = e.get("type", "unknown")
        by_edge_type[et] = by_edge_type.get(et, 0) + 1

    click.echo("\n" + "=" * 52)
    click.echo("  Knowledge Graph Summary")
    click.echo("=" * 52)
    click.echo(f"  Project:      {proj.get('name', 'N/A')}")
    click.echo(f"  Description:  {proj.get('description', 'N/A')}")
    click.echo(f"  Files:        {len(files)}")
    for cat, count in sorted(by_category.items()):
        click.echo(f"    {cat:<14} {count:>4}")
    click.echo(f"  Nodes:        {len(nodes)}")
    for nt, count in sorted(by_node_type.items(), key=lambda x: -x[1]):
        click.echo(f"    {nt:<14} {count:>4}")
    click.echo(f"  Edges:        {len(edges)}")
    for et, count in sorted(by_edge_type.items(), key=lambda x: -x[1]):
        click.echo(f"    {et:<14} {count:>4}")
    click.echo(f"  Layers:       {len(layers)}")
    for l in layers[:10]:
        click.echo(
            f"    - {l.get('name', '?')} "
            f"({len(l.get('nodeIds', []))} nodes)"
        )
    if len(layers) > 10:
        click.echo(f"    ... and {len(layers) - 10} more")
    click.echo(f"  Tour steps:   {len(tour)}")
    click.echo("=" * 52)


# ── Dashboard launcher ──────────────────────────────────────────────────


def _launch_dashboard(project_root: Path, plugin_root: Path) -> dict[str, str]:
    """Start the Vite dev server for the dashboard and capture its URL.

    Returns a dict with ``url`` and ``pid`` keys.
    """
    dashboard_dir = plugin_root / "packages" / "dashboard"
    if not dashboard_dir.exists():
        raise click.ClickException(
            f"Dashboard directory not found at {dashboard_dir}."
        )

    # Build dashboard if needed
    dist_dir = dashboard_dir / "dist"
    if not dist_dir.exists():
        click.echo("  Building dashboard UI...")
        r = subprocess.run(
            ["npx", "vite", "build"],
            cwd=str(dashboard_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode != 0:
            click.echo(
                "  Warning: dashboard build failed, "
                "trying dev server anyway."
            )
            _logger.warning(
                "dashboard build failed",
                stderr=r.stderr[:300],
            )

    # Start Vite dev server with GRAPH_DIR set
    env = os.environ.copy()
    env["GRAPH_DIR"] = str(project_root)

    click.echo("  Starting dashboard server...")

    proc = subprocess.Popen(
        ["npx", "vite", "--host", "127.0.0.1"],
        cwd=str(dashboard_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Read server output until we find the Dashboard URL
    url_line: str | None = None
    deadline = time.monotonic() + 30

    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.2)
            continue
        click.echo(f"    {line.rstrip()}")
        if "Dashboard URL:" in line and "http://" in line:
            url_line = line.strip()
            break
        if "http://127.0.0.1:" in line and "?token=" in line:
            url_line = line.strip()
            break
        # Also catch the "Local:" line Vite prints
        if "Local:" in line and "http://127.0.0.1:" in line:
            # This happens before the Dashboard URL line — keep reading
            continue

    # If we still haven't found it, give a few more tries
    if not url_line:
        for _ in range(20):
            line = proc.stdout.readline()
            if not line:
                break
            click.echo(f"    {line.rstrip()}")
            if "Dashboard URL:" in line or (
                "http://" in line and "?token=" in line
            ):
                url_line = line.strip()
                break
            time.sleep(0.5)

    if url_line:
        click.echo(f"\n  🚀  {url_line}")
    else:
        click.echo(
            "\n  Dashboard started — check terminal output for the URL."
        )
        url_line = "http://127.0.0.1:5173"

    return {
        "url": url_line,
        "pid": str(proc.pid),
    }


# ── Click command ───────────────────────────────────────────────────────


@click.command()
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Sandbox name (resolved from INDEX.toon).",
)
@click.option(
    "--path",
    type=str,
    default=None,
    help="Direct path to project directory.",
)
@click.option(
    "--no-dashboard",
    is_flag=True,
    default=False,
    help="Skip launching the interactive dashboard.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Force full rebuild, ignoring any existing graph.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed phase output (script stderr).",
)
def map(
    sandbox: str | None,
    path: str | None,
    no_dashboard: bool,
    full: bool,
    verbose: bool,
) -> None:
    """Run Understand Anything knowledge-graph generation on a project.

    Analyzes a codebase to produce an interactive knowledge graph with
    architectural layers and a guided tour, then launches the web dashboard.

    \b
    Pipeline:
      1.  SCAN — enumerate files, detect languages and categories
      2.  IMPORT MAP — resolve dependencies via tree-sitter
      3.  BATCH — cluster files into semantic batches (Louvain)
      4.  STRUCTURE — extract functions, classes, endpoints per batch
      5.  MERGE — combine batch graphs into unified knowledge graph
      6.  LAYERS + TOUR — build architectural layers and guided tour
      7.  VALIDATE — run inline graph validation
      8.  SAVE — write knowledge-graph.json, meta.json, fingerprints
      9.  DASHBOARD — launch interactive web visualisation

    \b
    Examples:

        hero map --sandbox my-project

        hero map --path ~/Development/my-project

        hero map --sandbox my-project --no-dashboard

        hero map --path /path/to/project --full
    """
    project_root = _resolve_sandbox_path(sandbox, path)

    click.echo(f"\n{'=' * 52}")
    click.echo(f"  hero map — {project_root.name}")
    click.echo(f"  Project:     {project_root}")
    click.echo(f"{'=' * 52}\n")

    # Prerequisites
    _check_nodejs()
    plugin_root = _check_understand_installed()
    _ensure_pnpm_built(plugin_root)

    click.echo(f"  Plugin root: {plugin_root}")
    click.echo(f"  Skill dir:   {UNDERSTAND_SKILL_DIR}")
    click.echo("")

    # Pipeline
    result = _run_pipeline(
        project_root=project_root,
        plugin_root=plugin_root,
        skill_dir=UNDERSTAND_SKILL_DIR,
    )

    kg_path = result.get("graph_path", "")
    if kg_path:
        click.echo(f"\n  Knowledge graph: {kg_path}")

    # Dashboard
    if not no_dashboard:
        click.echo("")
        try:
            dashboard = _launch_dashboard(project_root, plugin_root)
            if dashboard.get("pid"):
                click.echo(
                    f"  Server PID:  {dashboard['pid']}\n"
                    "  Press Ctrl+C in the terminal to stop it."
                )
        except click.ClickException as e:
            click.echo(f"  ⚠  Dashboard launch failed: {e}")
            click.echo(
                "  You can start it manually:\n"
                f"    cd {plugin_root / 'packages' / 'dashboard'}\n"
                f"    GRAPH_DIR={project_root} npx vite --host 127.0.0.1"
            )
    else:
        click.echo("\n  Dashboard launch skipped (--no-dashboard).")
        click.echo(
            "  To view the graph later:\n"
            f"    cd {plugin_root / 'packages' / 'dashboard'}\n"
            f"    GRAPH_DIR={project_root} npx vite --host 127.0.0.1"
        )

    click.echo("\n  Done.\n")
