"""hero tell — Natural language interface to HERO army.

Takes natural language from the user and converts it into
structured tasks for OpenClaw sessions_spawn.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from hero.state.index import IndexState
from hero.soldier.spawner import SoldierSpawner, get_model_for_role, load_army_config
from hero.soldier.context import BudgetConfig, KatanaData
from hero.soldier.dispatch import get_task, enqueue, list_all


# Intent patterns → role mapping
ROLE_KEYWORDS = {
    "lead": ["orchestrate", "coordinate", "manage", "oversee", "direct", "lead"],
    "architect": ["design", "plan", "architect", "structure", "spec", "blueprint", "layout"],
    "researcher": ["research", "find", "search", "look up", "investigate", "compare", "evaluate"],
    "archivist": ["document", "write docs", "readme", "changelog", "notes", "summarize"],
    "soldier": ["fix", "implement", "build", "code", "debug", "test", "update", "add", "remove", "change"],
}


def detect_role(task: str) -> str:
    """Detect the best role from natural language task description."""
    task_lower = task.lower()
    
    for role, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in task_lower:
                return role
    
    return "soldier"


def detect_sandboxes(task: str, index: IndexState) -> list[str]:
    """Detect which sandboxes the task mentions."""
    task_lower = task.lower()
    
    found = []
    for entry in index.list_sandboxes():
        name = entry["name"]
        if name.lower() in task_lower:
            found.append(name)
    
    return found


def break_down_task(task: str) -> list[str]:
    """Break a complex task into subtasks."""
    import re
    parts = re.split(r'\s+and\s+|\s*;\s*|\s+then\s+|\n+', task)
    parts = [p.strip() for p in parts if p.strip()]
    
    if len(parts) <= 1:
        return [task]
    
    return parts


@click.command()
@click.argument("message")
@click.option("--sandbox", "-s", default=None, help="Force target sandbox (overrides detection).")
@click.option("--role", "-r", default=None, help="Force role (overrides detection).")
@click.option("--dry-run", is_flag=True, help="Show what would happen without spawning.")
@click.option("--ask", "-a", is_flag=True, help="Ask clarifying questions before spawning.")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON (for OpenClaw consumption).")
@click.option("--spawn-cmd", is_flag=True, help="Show sessions_spawn-ready command.")
def tell(message: str, sandbox: str | None, role: str | None, 
         dry_run: bool, ask: bool, json_out: bool, spawn_cmd: bool) -> None:
    """Natural language interface to HERO army.

    Speak naturally — HERO figures out the rest. Outputs OpenClaw-ready
    tasks that can be executed via sessions_spawn.

    Examples:
        hero tell "fix the login bug in SOOK"
        hero tell "research Flutter state management for sook-pro"
        hero tell "design new API for Freya"
        hero tell "fix theme in SOOK and add dark mode to her"
        hero tell "fix bug" --ask
        hero tell "fix bug" --spawn-cmd   # show sessions_spawn command
    """
    index = IndexState()
    
    detected_role = role or detect_role(message)
    detected_sandboxes = detect_sandboxes(message, index)
    
    if sandbox:
        detected_sandboxes = [sandbox]
    
    if not detected_sandboxes:
        available = [e["name"] for e in index.list_sandboxes()]
        
        if ask:
            click.echo(f"I couldn't tell which project you mean.")
            click.echo(f"Available projects: {', '.join(available)}")
            answer = click.prompt("Which project?", type=str)
            for name in available:
                if name.lower() == answer.lower():
                    detected_sandboxes = [name]
                    break
            if not detected_sandboxes:
                click.echo(f"Unknown project: {answer}")
                return
        else:
            click.echo(f"Could not detect sandbox from: \"{message}\"")
            click.echo(f"Available sandboxes: {', '.join(available)}")
            click.echo(f"\nTry: hero tell \"fix bug in SOOK\"")
            click.echo(f"Or:  hero tell \"fix bug\" --ask")
            return
    
    subtasks = break_down_task(message)
    
    if ask:
        click.echo(f"\nI understood: \"{message}\"")
        click.echo(f"  Role: {detected_role}")
        click.echo(f"  Project(s): {', '.join(detected_sandboxes)}")
        click.echo(f"  Subtasks: {len(subtasks)}")
        
        confirm = click.confirm("Is this correct?", default=True)
        if not confirm:
            new_role = click.prompt("Role (lead/architect/soldier/researcher/archivist/utility)", 
                                   default=detected_role, type=str)
            new_sandbox = click.prompt("Project name", 
                                      default=detected_sandboxes[0], type=str)
            new_task = click.prompt("Task description", default=message, type=str)
            
            detected_role = new_role
            detected_sandboxes = [new_sandbox]
            subtasks = [new_task]
            message = new_task
    
    model_full, model_short = get_model_for_role(detected_role)
    
    # Show what we understood
    click.echo("\n" + "═" * 50)
    click.echo("  HERO ⚡ — Army Intent (OpenClaw-native)")
    click.echo("═" * 50)
    click.echo(f"  Input:    \"{message}\"")
    click.echo(f"  Role:     {detected_role}")
    click.echo(f"  Model:    {model_full}")
    click.echo(f"  Sandboxes: {', '.join(detected_sandboxes)}")
    click.echo(f"  Subtasks: {len(subtasks)}")
    for i, st in enumerate(subtasks, 1):
        click.echo(f"    {i}. {st}")
    click.echo("═" * 50)
    
    if dry_run:
        click.echo("\n[DRY RUN] No tasks queued.")
        click.echo("Run without --dry-run to queue tasks for OpenClaw.")
        return
    
    # Queue tasks
    click.echo()
    results = []
    
    for sbx_name in detected_sandboxes:
        entry = index.get_sandbox(sbx_name)
        if not entry:
            click.echo(f"  [SKIP] Sandbox '{sbx_name}' not found")
            continue
        
        sandbox_path = Path(entry["path"])
        if not sandbox_path.exists():
            click.echo(f"  [SKIP] Path doesn't exist: {sandbox_path}")
            continue
        
        task = subtasks[0] if len(subtasks) == 1 else f"Complete these tasks in order: {'; '.join(subtasks)}"
        
        budget_config = BudgetConfig(
            bootstrap_max=5000,
            compactions_used=0,
            tokens_remaining=5000,
        )
        
        spawner = SoldierSpawner(sandbox_path)
        try:
            task_id = spawner.launch(
                task=task,
                budget=budget_config,
                role=detected_role,
                model_override=(model_full, model_short),
            )
            results.append({"sandbox": sbx_name, "status": "ok", "id": task_id})
            
            # Show sessions_spawn-ready info
            task_data = get_task(task_id)
            click.echo(f"  [OK] {sbx_name}: {detected_role} queued")
            click.echo(f"       Task ID: {task_id}")
            click.echo(f"       Model: {model_full}")
            click.echo(f"       Label: {task_data.get('label', '')}")
            
            if spawn_cmd:
                from hero.soldier.dispatch import get_sessions_spawn_command
                cmd = get_sessions_spawn_command(task_data)
                click.echo(f"\n  sessions_spawn ready:")
                click.echo(f"    sessions_spawn")
                click.echo(f"      --label \"{cmd['label']}\"")
                click.echo(f"      --model {cmd['model']}")
                click.echo(f"      --mode {cmd['mode']}")
                click.echo(f"      --runtime {cmd['runtime']}")
                click.echo(f"      --runTimeoutSeconds {cmd['runTimeoutSeconds']}")
                click.echo(f"      --task \"{cmd['task'][:60]}...\"")
                
        except Exception as e:
            results.append({"sandbox": sbx_name, "status": "error", "error": str(e)})
            click.echo(f"  [FAIL] {sbx_name}: {e}")
    
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = sum(1 for r in results if r["status"] == "error")
    click.echo(f"\n  Queued: {ok} succeeded, {fail} failed")
    click.echo("═" * 50)
    
    # JSON output for programmatic consumption
    if json_out:
        click.echo(json.dumps(results, indent=2))


if __name__ == "__main__":
    tell()