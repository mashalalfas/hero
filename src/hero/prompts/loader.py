"""Prompt template loader — reads .md files from ~/.hero/prompts/ or bundled defaults.

Templates use Python string.Template syntax ($variable, ${variable}).
User templates in ~/.hero/prompts/ override bundled defaults in src/hero/prompts/defaults/.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

PROMPTS_DIR = Path.home() / ".hero" / "prompts"
DEFAULTS_DIR = Path(__file__).parent / "defaults"


def _resolve_template(relative_path: str) -> str:
    """Load template content, checking user dir first, then bundled defaults.

    Args:
        relative_path: e.g. "roles/soldier.md", "phases/verify.md"

    Returns:
        Template content as string.

    Raises:
        FileNotFoundError: If template not found in either location.
    """
    user_path = PROMPTS_DIR / relative_path
    if user_path.exists():
        return user_path.read_text()

    default_path = DEFAULTS_DIR / relative_path
    if default_path.exists():
        return default_path.read_text()

    raise FileNotFoundError(
        f"Prompt template not found: {relative_path}\n"
        f"Checked: {user_path} and {default_path}"
    )


def render_template(relative_path: str, **variables: str | int | float) -> str:
    """Load and render a prompt template with the given variables.

    Args:
        relative_path: e.g. "roles/soldier.md", "phases/verify.md"
        **variables: Template variables (sandbox, task, model, etc.)

    Returns:
        Rendered prompt string.
    """
    content = _resolve_template(relative_path)
    template = Template(content)
    return template.safe_substitute(**variables)


def load_rule(rule_name: str) -> str:
    """Load a rule block from rules/ directory.

    Args:
        rule_name: e.g. "tdd", "context-budget", "code-style"

    Returns:
        Rule content as string, or empty string if not found.
    """
    try:
        return _resolve_template(f"rules/{rule_name}.md").strip()
    except FileNotFoundError:
        return ""
