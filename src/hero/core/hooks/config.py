"""Hooks YAML configuration loader.

Loads ``~/.openclaw/hooks/hooks.yaml`` and validates each hook entry.
Supports the ``enabled`` field for toggling hooks on/off without
removing them from the config.

Hook config structure::

    hooks:
      - event: on_session_start
        hook_id: read_memory
        rule: "Read MEMORY.md and log session start"
        action: warn         # block | warn | silent
        max_tokens: 500
        cache_ttl: 0         # seconds, 0 = no cache
        script: events/on_session_start.sh
        enabled: true        # optional, defaults to true
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_HOOKS_CONFIG = Path.home() / ".openclaw" / "hooks" / "hooks.yaml"
VALID_ACTIONS = {"block", "warn", "silent"}
VALID_EVENTS = {
    "on_session_start",
    "before_exec",
    "before_sessions_yield",
    "before_spawn",
    "before_shutdown",
}


@dataclass
class HookConfig:
    """Validated hook configuration entry."""

    event: str
    hook_id: str
    rule: str
    action: str  # block | warn | silent
    max_tokens: int
    cache_ttl: int  # seconds, 0 = no cache
    script: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.action not in VALID_ACTIONS:
            raise ValueError(
                f"Hook {self.hook_id!r}: action must be one of "
                f"{sorted(VALID_ACTIONS)}, got {self.action!r}",
            )
        if self.event not in VALID_EVENTS:
            raise ValueError(
                f"Hook {self.hook_id!r}: event must be one of "
                f"{sorted(VALID_EVENTS)}, got {self.event!r}",
            )
        if self.max_tokens < 0:
            raise ValueError(
                f"Hook {self.hook_id!r}: max_tokens must be >= 0",
            )
        if self.cache_ttl < 0:
            raise ValueError(
                f"Hook {self.hook_id!r}: cache_ttl must be >= 0",
            )

    @property
    def config_dir(self) -> Path:
        """Directory containing hooks.yaml (for script path resolution)."""
        return DEFAULT_HOOKS_CONFIG.parent

    @property
    def script_path(self) -> Path:
        """Absolute path to the hook's executable script."""
        p = Path(self.script)
        if p.is_absolute():
            return p
        return (self.config_dir / p).resolve()

    @property
    def tier(self) -> str:
        """Failure tier: ``block`` → CRITICAL, ``warn`` → IMPORTANT, ``silent`` → OPTIONAL."""
        return {
            "block": "CRITICAL",
            "warn": "IMPORTANT",
            "silent": "OPTIONAL",
        }[self.action]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "hook_id": self.hook_id,
            "rule": self.rule,
            "action": self.action,
            "max_tokens": self.max_tokens,
            "cache_ttl": self.cache_ttl,
            "script": self.script,
            "enabled": self.enabled,
        }


def load_hooks_config(path: Path | None = None) -> list[HookConfig]:
    """Load and validate hook configurations from a YAML file.

    Args:
        path: Path to hooks.yaml.  Defaults to
              ``~/.openclaw/hooks/hooks.yaml``.

    Returns:
        List of validated ``HookConfig`` instances.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
        ValueError: If any hook entry fails validation.
    """
    config_path = path or DEFAULT_HOOKS_CONFIG

    if not config_path.exists():
        return []

    raw = yaml.safe_load(config_path.read_text()) or {}
    entries = raw.get("hooks", [])

    hooks: list[HookConfig] = []
    seen_ids: set[str] = set()

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Hook entry {i} is not a mapping: {entry!r}",
            )

        hook_id = entry.get("hook_id", f"unnamed-{i}")
        if hook_id in seen_ids:
            raise ValueError(
                f"Duplicate hook_id {hook_id!r} at entry {i}",
            )
        seen_ids.add(hook_id)

        hooks.append(
            HookConfig(
                event=entry.get("event", "on_session_start"),
                hook_id=hook_id,
                rule=entry.get("rule", ""),
                action=entry.get("action", "warn"),
                max_tokens=entry.get("max_tokens", 500),
                cache_ttl=entry.get("cache_ttl", 0),
                script=entry.get("script", ""),
                enabled=entry.get("enabled", True),
            ),
        )

    return hooks


def get_hooks_for_event(
    hooks: list[HookConfig],
    event: str,
) -> list[HookConfig]:
    """Filter hooks by event type.

    Args:
        hooks: All loaded hook configs.
        event: Event name (e.g. ``on_session_start``).

    Returns:
        Hooks matching *event*, sorted by action priority
        (cheapest first: silent < warn < block).
    """
    priority = {"silent": 0, "warn": 1, "block": 2}
    matching = [h for h in hooks if h.event == event and h.enabled]
    matching.sort(key=lambda h: priority.get(h.action, 0))
    return matching
