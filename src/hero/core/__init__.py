"""
hero.core — Shared utility functions for HERO CLI commands.

These are the canonical implementations of project detection, sandbox
resolution, and subprocess execution.  All command modules should import
from here instead of copy-pasting or reimplementing.
"""

from hero.core.project import detect_project_type, resolve_sandbox
from hero.core.subprocess import safe_run

__all__ = ["detect_project_type", "resolve_sandbox", "safe_run"]
