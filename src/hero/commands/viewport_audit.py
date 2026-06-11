"""hero viewport — Show context window (viewport) for all configured models.

Diagnostic tool to compare what's in army.yaml / models.json vs what
the session actually reports. Helps debug context window mismatches.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

# Paths to check
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
OPENCLAW_MODELS_JSON = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "models.json"
HERO_ARMY = Path.home() / ".hero" / "army.yaml"
HERO_CONFIG = Path.home() / ".hero" / "army.yaml"


def _load_openclaw_providers() -> dict:
    """Load model providers from OpenClaw config."""
    if not OPENCLAW_CONFIG.exists():
        return {}
    try:
        with open(OPENCLAW_CONFIG) as f:
            d = json.load(f)
        return d.get("models", {}).get("providers", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _load_openclaw_defaults() -> dict:
    """Load agents.defaults.models from OpenClaw config."""
    if not OPENCLAW_CONFIG.exists():
        return {}
    try:
        with open(OPENCLAW_CONFIG) as f:
            d = json.load(f)
        return d.get("agents", {}).get("defaults", {}).get("models", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _load_models_json() -> dict:
    """Load the runtime models.json."""
    if not OPENCLAW_MODELS_JSON.exists():
        return {}
    try:
        with open(OPENCLAW_MODELS_JSON) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _load_army_models() -> dict:
    """Load model assignments from HERO army.yaml."""
    import yaml
    if not HERO_ARMY.exists():
        return {}
    try:
        with open(HERO_ARMY) as f:
            army = yaml.safe_load(f)
        models = {}
        roles = army.get("roles", {})
        for role, conf in roles.items():
            if "model" in conf:
                provider = conf.get("provider", "")
                model = conf["model"]
                ctx = conf.get("context_window", "?")
                models[f"{provider}/{model}"] = {"role": role, "context_window": ctx}
            if "models" in conf:
                for m in conf["models"]:
                    provider = m.get("provider", "")
                    model = m["model"]
                    ctx = m.get("context_window", "?")
                    models[f"{provider}/{model}"] = {"role": role, "context_window": ctx}
        return models
    except (yaml.YAMLError, OSError):
        return {}


@click.command()
@click.option("--json", "json_out", is_flag=True, help="Output as JSON.")
def viewport(json_out: bool) -> None:
    """Show context windows (viewport) for all configured models.

    Compares:
    - army.yaml (HERO roles)
    - openclaw.json (provider definitions)
    - agents.defaults.models (model allowlist)
    - models.json (runtime registry)

    Helps debug context window mismatches between config and what
    the session actually reports.
    """
    # Load all sources
    oc_providers = _load_openclaw_providers()
    oc_defaults = _load_openclaw_defaults()
    runtime = _load_models_json()
    army_models = _load_army_models()

    # Collect all unique model IDs
    all_models = {}

    # From OpenClaw providers
    for pname, pconf in oc_providers.items():
        for m in pconf.get("models", []):
            mid = f"{pname}/{m['id']}"
            ctx = m.get("contextWindow", "?")
            all_models[mid] = {
                "provider": pname,
                "model": m["id"],
                "oc_context": ctx,
                "in_defaults": mid in oc_defaults,
                "in_army": mid in army_models,
                "army_role": army_models.get(mid, {}).get("role", "—"),
                "army_ctx": army_models.get(mid, {}).get("context_window", "—"),
                "runtime_ctx": "?",
            }

    # From army models not in OpenClaw providers
    for mid, info in army_models.items():
        if mid not in all_models:
            all_models[mid] = {
                "provider": mid.split("/")[0],
                "model": mid.split("/")[1] if "/" in mid else mid,
                "oc_context": "NOT IN OPENCLAW",
                "in_defaults": False,
                "in_army": True,
                "army_role": info["role"],
                "army_ctx": info["context_window"],
                "runtime_ctx": "?",
            }

    # From runtime models.json
    runtime_providers = runtime.get("providers", {})
    for pname, pconf in runtime_providers.items():
        for m in pconf.get("models", []):
            mid = f"{pname}/{m['id']}"
            if mid in all_models:
                all_models[mid]["runtime_ctx"] = m.get("contextWindow", "?")
            else:
                all_models[mid] = {
                    "provider": pname,
                    "model": m["id"],
                    "oc_context": "?",
                    "in_defaults": mid in oc_defaults,
                    "in_army": mid in army_models,
                    "army_role": "—",
                    "army_ctx": "—",
                    "runtime_ctx": m.get("contextWindow", "?"),
                }

    if json_out:
        click.echo(json.dumps(all_models, indent=2))
        return

    # Display
    click.echo()
    click.echo("═" * 80)
    click.echo("  HERO VIEWPORT — Context Window Audit")
    click.echo("═" * 80)
    click.echo()

    # Header
    click.echo(f"  {'Model':<40s}  {'OC Config':>10s}  {'Runtime':>10s}  {'Army':>10s}  {'Role':<12s}")
    click.echo("  " + "─" * 80)

    for mid, info in sorted(all_models.items()):
        oc_ctx = info["oc_context"]
        run_ctx = info["runtime_ctx"]
        army_ctx = info["army_ctx"]
        role = info["army_role"]

        # Color coding: green if match, red if mismatch
        oc_str = f"{oc_ctx:>10}" if isinstance(oc_ctx, (int, float)) else f"{str(oc_ctx)[:10]:>10}"
        run_str = f"{run_ctx:>10}" if isinstance(run_ctx, (int, float)) else f"{str(run_ctx)[:10]:>10}"
        army_str = f"{army_ctx:>10}" if isinstance(army_ctx, (int, float)) else f"{str(army_ctx)[:10]:>10}"

        # Check mismatches
        oc_val = oc_ctx if isinstance(oc_ctx, (int, float)) else 0
        run_val = run_ctx if isinstance(run_ctx, (int, float)) else 0
        army_val = army_ctx if isinstance(army_ctx, (int, float)) else 0

        mismatch = (oc_val != run_val and run_val > 0) or (oc_val != army_val and army_val > 0)
        icon = "⚠️" if mismatch else "✅"

        click.echo(f"  {icon} {mid:<38s}  {oc_str}  {run_str}  {army_str}  {role}")

    click.echo()
    click.echo("═" * 80)
    click.echo("  ⚠️ = context mismatch between OpenClaw config, runtime, or army")
    click.echo("  ✅ = all sources agree")
    click.echo()
    click.echo("  Session context shown in /status may differ — sessions are capped")
    click.echo("  by the model active at session creation, not the current override.")
    click.echo("═" * 80)
    click.echo()


if __name__ == "__main__":
    viewport()
