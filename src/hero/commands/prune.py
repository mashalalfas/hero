"""hero prune — Clean up a pipeline worktree and its git branch.

Removes the worktree created by ``hero go`` for a specific pipeline,
prunes stale git refs, and optionally removes the pipeline branch.

Usage:
    hero prune <pipeline_id>
    hero prune <pipeline_id> --force   # remove even if uncommitted changes

Examples:
    hero prune abc12345       # clean up worktree for pipeline abc12345
    hero prune abc12345 -f     # force-remove with uncommitted changes
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click

from hero.state.index import IndexState

WORKTREE_BASE = Path.home() / "Development" / "worktrees"
PIPELINE_DIR = Path.home() / ".hero" / "pipeline"


@click.command("prune")
@click.argument("pipeline_id")
@click.option(
    "--force",
    is_flag=True,
    help="Force-remove worktree even with uncommitted changes.",
)
def prune(pipeline_id: str, force: bool) -> None:
    """Remove a pipeline worktree and clean up git refs.

    Reads the pipeline manifest to find the worktree path, then:
    1. Removes the worktree directory
    2. Prunes stale git worktree refs
    3. Optionally deletes the pipeline branch

    The pipeline branch (hero/<pipeline_id>) is NOT deleted by default,
    so you can recover commits if needed. Use --force to delete the branch.
    """
    # Load manifest
    manifest_path = PIPELINE_DIR / f"{pipeline_id}.json"
    if not manifest_path.exists():
        # Try to find by prefix
        matches = list(PIPELINE_DIR.glob(f"{pipeline_id}*.json"))
        if len(matches) == 1:
            manifest_path = matches[0]
        elif len(matches) > 1:
            raise click.ClickException(
                f"Multiple pipelines match '{pipeline_id}':\n"
                + "\n".join(f"  {m.stem}" for m in matches)
            )
        else:
            raise click.ClickException(
                f"Pipeline manifest not found for '{pipeline_id}'.\n"
                f"  Looked in: {PIPELINE_DIR}"
            )

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(f"Failed to read manifest: {exc}")

    sandbox = manifest.get("sandbox", "")
    worktree_path = manifest.get("steps", {}).get("worktree", {}).get("path")
    pipeline_branch = manifest.get("steps", {}).get("worktree", {}).get(
        "branch", f"hero/{pipeline_id}"
    )

    # Resolve sandbox path for git operations
    index = IndexState()
    entry = index.get_sandbox(sandbox)
    if not entry:
        # Fallback: try common location
        sandbox_path = Path(f"~/Development/{sandbox}").expanduser()
    else:
        sandbox_path = Path(entry["path"])

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"HERO PRUNE — {pipeline_id[:12]}")
    click.echo("=" * 60)
    click.echo(f"  Sandbox:     {sandbox}")
    click.echo(f"  Branch:      {pipeline_branch}")
    if worktree_path:
        click.echo(f"  Worktree:    {worktree_path}")
    else:
        click.echo(f"  Worktree:    (not recorded — scanning defaults)")
        # Try default location
        worktree_path = str(WORKTREE_BASE / sandbox / pipeline_id)
        if not Path(worktree_path).exists():
            click.echo(f"  ⚠ No worktree found at default location either")
            worktree_path = None
    click.echo(f"  Force:       {'yes' if force else 'no'}")
    click.echo("=" * 60)
    click.echo("")

    if not worktree_path:
        click.echo("Nothing to prune — no worktree path recorded or found.")
        return

    worktree_path_obj = Path(worktree_path)

    # ── Step 1: Remove worktree ────────────────────────────────────────
    if worktree_path_obj.exists():
        click.echo("── Step 1: Remove worktree ───────────────────────")
        flags = [] if force else ["-f"]
        result = subprocess.run(
            ["git", "worktree", "remove", *flags, str(worktree_path_obj)],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            click.echo(f"  ✅ Removed worktree directory")
        else:
            err = result.stderr.strip()
            if "uncommitted changes" in err.lower() and not force:
                click.echo(f"  ⚠ Worktree has uncommitted changes — use --force to remove")
                click.echo(f"     Error: {err[:120]}")
                return
            else:
                click.echo(f"  ⚠ git worktree remove returned: {err[:120]}")
                # Try manual removal
                try:
                    import shutil
                    shutil.rmtree(worktree_path_obj, ignore_errors=True)
                    click.echo(f"  ✅ Force-removed directory")
                except Exception as exc:
                    click.echo(f"  ❌ Failed to remove directory: {exc}")
                    return
    else:
        click.echo("── Step 1: Worktree directory already gone ───────")

    # ── Step 2: Prune stale refs ───────────────────────────────────────
    click.echo("── Step 2: Prune git refs ────────────────────────")
    result = subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(sandbox_path),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        click.echo(f"  ✅ Pruned stale worktree references")
    else:
        click.echo(f"  ⚠ git worktree prune: {result.stderr.strip()[:80]}")

    # ── Step 3: Optionally delete pipeline branch ─────────────────────
    if force:
        click.echo("── Step 3: Delete pipeline branch ───────────────")
        result = subprocess.run(
            ["git", "branch", "-D", pipeline_branch],
            cwd=str(sandbox_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            click.echo(f"  ✅ Deleted branch {pipeline_branch}")
        else:
            err = result.stderr.strip()
            if "not found" in err.lower() or "does not exist" in err.lower():
                click.echo(f"  Branch already deleted")
            else:
                click.echo(f"  ⚠ Could not delete branch: {err[:120]}")
    else:
        click.echo("── Step 3: Keep pipeline branch ──────────────────")
        click.echo(f"  Branch '{pipeline_branch}' preserved (recover commits with: git checkout {pipeline_branch})")

    # ── Step 4: Clean up manifest ──────────────────────────────────────
    click.echo("── Step 4: Clean pipeline manifest ───────────────")
    try:
        manifest_data = json.loads(manifest_path.read_text())
        manifest_data["status"] = "pruned"
        manifest_data["pruned_at"] = click.get_current_context().obj.get(
            "now_iso", ""
        ) if hasattr(click, 'get_current_context') else ""
        manifest_data["pruned_by"] = "hero prune"
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        click.echo(f"  ✅ Manifest updated: {manifest_path}")
    except Exception as exc:
        click.echo(f"  ⚠ Could not update manifest: {exc}")

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"✅ PRUNED — {pipeline_id[:12]}")
    click.echo(f"  Worktree removed, refs pruned")
    if force:
        click.echo(f"  Branch deleted")
    else:
        click.echo(f"  Branch preserved for recovery")
    click.echo("=" * 60)
