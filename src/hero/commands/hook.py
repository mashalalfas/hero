"""hero hook — HERO Hook System CLI.

Manage the git-hooks-for-AI hook system that enforces agent behaviour
rules through declarative configuration, event scripts, and tiered
failure handling.

Commands:
    hero hook list              Show all hooks with status
    hero hook run <event>       Execute hooks for an event
    hero hook test <event>      Dry-run, show what would execute
    hero hook enable <hook_id>  Enable a disabled hook
    hero hook disable <hook_id> Disable a hook without removing config
    hero hook cache clear       Invalidate entire hook cache
    hero hook cache stats       Show cache hit/miss stats
"""

from __future__ import annotations

from pathlib import Path, PurePath

import click

from hero.core.hooks.cache import hook_cache
from hero.core.hooks.circuit import hook_circuit
from hero.core.hooks.config import DEFAULT_HOOKS_CONFIG, get_hooks_for_event, load_hooks_config
from hero.core.hooks.runner import HookRunner


@click.group()
def hook() -> None:
    """Manage HERO hook system.

    Hooks are git-hooks-for-AI: declarative rules that enforce agent
    behaviour through POSIX shell scripts.

    Config: ~/.openclaw/hooks/hooks.yaml
    Scripts: ~/.openclaw/hooks/events/
    """
    pass


@hook.command("list")
def list_hooks() -> None:
    """Show all configured hooks with their status.

    Displays hook_id, event, action/tier, cache TTL, max tokens,
    and whether the hook script exists and is executable.
    """
    try:
        hooks = load_hooks_config()
    except FileNotFoundError:
        click.echo("No hooks config found at ~/.openclaw/hooks/hooks.yaml")
        return

    if not hooks:
        click.echo("No hooks configured.")
        return

    degraded = {c.hook_id for c in hook_circuit.get_degraded()}

    click.echo(f"Hooks: {len(hooks)} configured\n")

    # Header
    click.echo(
        f"{'HOOK ID':<28} {'EVENT':<24} {'TIER':<10} "
        f"{'CACHE':<8} {'TOKENS':<8} STATUS",
    )
    click.echo("-" * 100)

    for h in hooks:
        script = h.script_path
        if script.exists() and script.stat().st_mode & 0o111:
            status = "✅ ready"
        elif script.exists():
            status = "⚠️  not executable"
        else:
            status = "❌ script missing"

        if not h.enabled:
            status = "⏸  disabled"
        elif h.hook_id in degraded:
            status = "🔴 degraded"

        cache = f"{h.cache_ttl}s" if h.cache_ttl > 0 else "none"

        click.echo(
            f"{h.hook_id:<28} {h.event:<24} {h.tier:<10} "
            f"{cache:<8} {h.max_tokens:<8} {status}",
        )

    # Show degraded hooks detail
    if degraded:
        click.echo(f"\n🔴 {len(degraded)} hook(s) degraded. "
                    f"Run next on_session_start to reset.")


@hook.command("run")
@click.argument("event", type=str)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to hooks.yaml (default: ~/.openclaw/hooks/hooks.yaml)",
)
@click.option(
    "--context",
    "-c",
    type=str,
    multiple=True,
    help="Key=value context pairs passed to scripts (repeatable).",
)
def run_hook(event: str, config: Path | None, context: tuple[str, ...]) -> None:
    """Execute all enabled hooks for EVENT.

    Events: on_session_start, before_exec, before_sessions_yield,
            before_spawn, before_shutdown

    Examples:
        hero hook run on_session_start
        hero hook run before_exec -c task="fix bug" -c sandbox="my-app"
    """
    try:
        hooks = load_hooks_config(config)
    except Exception as exc:
        click.echo(f"Error loading config: {exc}", err=True)
        raise SystemExit(1)

    ctx_dict = {}
    for pair in context:
        if "=" in pair:
            k, v = pair.split("=", 1)
            ctx_dict[k] = v

    runner = HookRunner(hooks)

    matching = get_hooks_for_event(hooks, event)
    if not matching:
        click.echo(f"No enabled hooks for event: {event}")
        return

    click.echo(f"Running {len(matching)} hook(s) for event: {event}\n")

    results = runner.run_event(event, ctx_dict)

    ok = 0
    failed = 0
    degraded = 0
    cached = 0

    for r in results:
        icon = "✅" if r.success else "🔴" if r.degraded else "⚠️"
        cache_mark = " [cached]" if r.cached else ""
        click.echo(
            f"  {icon} {r.hook_id:<28} "
            f"{r.duration_ms:6.0f}ms  exit={r.exit_code}{cache_mark}",
        )
        if r.stderr.strip():
            for line in r.stderr.strip().split("\n")[:3]:
                click.echo(f"      stderr: {line}")
        if r.error:
            click.echo(f"      error: {r.error}")

        if r.success:
            ok += 1
        elif r.degraded:
            degraded += 1
        else:
            failed += 1

    click.echo(
        f"\nResults: {ok} ok, {failed} failed, "
        f"{degraded} degraded, {cached} cached",
    )


@hook.command("test")
@click.argument("event", type=str)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to hooks.yaml (default: ~/.openclaw/hooks/hooks.yaml)",
)
def test_hook(event: str, config: Path | None) -> None:
    """Dry-run: show what hooks would execute for EVENT.

    Validates config, checks script existence, shows circuit breaker
    status, but does NOT execute any scripts.
    """
    try:
        hooks = load_hooks_config(config)
    except Exception as exc:
        click.echo(f"Error loading config: {exc}", err=True)
        raise SystemExit(1)

    matching = get_hooks_for_event(hooks, event)
    if not matching:
        click.echo(f"No enabled hooks for event: {event}")
        return

    click.echo(f"Would run {len(matching)} hook(s) for event: {event}\n")

    for h in matching:
        # Circuit breaker check
        if hook_circuit.is_degraded(h.hook_id):
            status = "🔴 SKIP (degraded)"
        elif not h.script_path.exists():
            status = "❌ SKIP (script missing)"
        elif not (h.script_path.stat().st_mode & 0o111):
            status = "⚠️  SKIP (not executable)"
        else:
            status = "✅ WOULD RUN"

        cache = f"{h.cache_ttl}s" if h.cache_ttl > 0 else "none"
        click.echo(
            f"  {h.hook_id:<28} tier={h.tier:<10} "
            f"cache={cache:<6} tokens={h.max_tokens:<5} {status}",
        )
        click.echo(f"      script: {PurePath(h.script)}")

    if not matching:
        click.echo("  (none)")


@hook.command("enable")
@click.argument("hook_id", type=str)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to hooks.yaml (default: ~/.openclaw/hooks/hooks.yaml)",
)
def enable_hook(hook_id: str, config: Path | None) -> None:
    """Enable a disabled hook by hook_id.

    Modifies hooks.yaml in place, setting enabled: true.
    """
    import yaml

    config_path = config or DEFAULT_HOOKS_CONFIG
    if not config_path.exists():
        click.echo(f"Config not found: {config_path}", err=True)
        raise SystemExit(1)

    raw = yaml.safe_load(config_path.read_text()) or {}
    entries = raw.get("hooks", [])

    found = False
    for entry in entries:
        if entry.get("hook_id") == hook_id:
            entry["enabled"] = True
            found = True
            break

    if not found:
        click.echo(f"Hook not found: {hook_id}", err=True)
        raise SystemExit(1)

    config_path.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True))
    click.echo(f"Enabled: {hook_id}")


@hook.command("disable")
@click.argument("hook_id", type=str)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to hooks.yaml (default: ~/.openclaw/hooks/hooks.yaml)",
)
def disable_hook(hook_id: str, config: Path | None) -> None:
    """Disable a hook by hook_id without removing it from config.

    Modifies hooks.yaml in place, setting enabled: false.
    """
    import yaml

    config_path = config or DEFAULT_HOOKS_CONFIG
    if not config_path.exists():
        click.echo(f"Config not found: {config_path}", err=True)
        raise SystemExit(1)

    raw = yaml.safe_load(config_path.read_text()) or {}
    entries = raw.get("hooks", [])

    found = False
    for entry in entries:
        if entry.get("hook_id") == hook_id:
            entry["enabled"] = False
            found = True
            break

    if not found:
        click.echo(f"Hook not found: {hook_id}", err=True)
        raise SystemExit(1)

    config_path.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True))
    click.echo(f"Disabled: {hook_id}")


@hook.group("cache")
def cache_group() -> None:
    """Manage hook result cache."""
    pass


@cache_group.command("clear")
@click.option(
    "--hook-id",
    type=str,
    default=None,
    help="Clear cache for a specific hook (default: all hooks).",
)
def cache_clear(hook_id: str | None) -> None:
    """Invalidate the hook result cache.

    Use --hook-id to clear only a specific hook's cache.
    """
    count = hook_cache.clear(hook_id)
    if hook_id:
        click.echo(f"Cache cleared for hook: {hook_id} ({count} file(s))")
    else:
        click.echo(f"Cache cleared: {count} file(s) removed")


@cache_group.command("stats")
def cache_stats() -> None:
    """Show cache hit/miss/expired/set statistics."""
    stats = hook_cache.stats
    total = stats["hits"] + stats["misses"]
    hit_rate = f"{stats['hits'] / total * 100:.1f}%" if total > 0 else "N/A"

    click.echo("Hook Cache Statistics")
    click.echo("-" * 30)
    click.echo(f"  Hits:    {stats['hits']}")
    click.echo(f"  Misses:  {stats['misses']}")
    click.echo(f"  Expired: {stats['expired']}")
    click.echo(f"  Sets:    {stats['sets']}")
    click.echo(f"  Hit rate: {hit_rate}")


if __name__ == "__main__":
    hook()
