"""Tests for hero.core — the shared utility functions for HERO CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from hero.core.project import (
    detect_project_type,
    resolve_sandbox,
    SANDBOX_DIR,
    INDEX_PATH,
    DEVELOPMENT_DIR,
    _parse_index_toon,
)
from hero.core.subprocess import safe_run


# ═══════════════════════════════════════════════════════════════════════════
# detect_project_type
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectProjectType:
    """Project type detection from marker files."""

    def test_flutter(self, tmp_path: Path) -> None:
        (tmp_path / "pubspec.yaml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "flutter"
        assert result["analyze_cmd"] == ["flutter", "analyze"]
        assert result["build_cmd"] == ["flutter", "build", "apk", "--debug"]
        assert result["analyzer"] == "flutter"
        assert result["source_globs"] == ["lib/**/*.dart"]

    def test_node(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"scripts": {"lint": "eslint ."}}')
        result = detect_project_type(tmp_path)
        assert result["type"] == "node"
        assert result["analyze_cmd"] == ["npm", "run", "lint"]
        assert result["build_cmd"] == ["npm", "run", "build"]
        assert result["analyzer"] == "npm"
        assert "src/**/*.js" in result["source_globs"]

    def test_node_no_lint_script(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        result = detect_project_type(tmp_path)
        assert result["type"] == "node"
        assert result["analyze_cmd"] is None

    def test_electron(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"electron": "^28.0.0"}})
        )
        result = detect_project_type(tmp_path)
        assert result["type"] == "electron"
        assert result["analyze_cmd"] == ["npx", "tsc", "--noEmit"]
        assert result["build_cmd"] == ["npx", "vite", "build"]
        assert result["analyzer"] == "tsc"
        assert "src/**/*.ts" in result["source_globs"]

    def test_electron_in_dev_deps(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"electron": "^28.0.0"}})
        )
        result = detect_project_type(tmp_path)
        assert result["type"] == "electron"

    def test_python(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "python"
        assert result["analyze_cmd"] == ["ruff", "check", "."]
        assert result["build_cmd"] == ["python", "-m", "compileall", "."]
        assert "**/*.py" in result["source_globs"]

    def test_rust(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "rust"
        assert result["analyze_cmd"] == ["cargo", "check"]
        assert result["build_cmd"] == ["cargo", "build", "--release"]
        assert result["analyzer"] == "cargo"
        assert "**/*.rs" in result["source_globs"]

    def test_godot_project(self, tmp_path: Path) -> None:
        (tmp_path / "project.godot").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "godot"
        assert result["analyze_cmd"] is None
        assert result["build_cmd"] is None
        assert "**/*.gd" in result["source_globs"]

    def test_godot_engine_cfg(self, tmp_path: Path) -> None:
        (tmp_path / "engine.cfg").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "godot"

    def test_unknown(self, tmp_path: Path) -> None:
        result = detect_project_type(tmp_path)
        assert result["type"] == "unknown"
        assert result["analyze_cmd"] is None
        assert result["build_cmd"] is None
        assert result["analyzer"] is None
        assert result["source_globs"] is None

    def test_corrupt_package_json(self, tmp_path: Path) -> None:
        """Corrupt package.json should still return 'node' type (graceful fallback)."""
        (tmp_path / "package.json").write_text("not valid json {{{")
        result = detect_project_type(tmp_path)
        assert result["type"] == "node"
        # Analyze/build commands should be conservative defaults
        assert result["analyze_cmd"] is None  # can't inspect scripts
        assert result["build_cmd"] == ["npm", "run", "build"]

    # ── Specificity ordering ──────────────────────────────────────────

    def test_flutter_beats_others(self, tmp_path: Path) -> None:
        """If both pubspec.yaml and package.json exist, Flutter wins."""
        (tmp_path / "pubspec.yaml").write_text("")
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "Cargo.toml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "flutter"

    def test_node_beats_python(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "Cargo.toml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "node"

    def test_python_beats_rust(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "Cargo.toml").write_text("")
        result = detect_project_type(tmp_path)
        assert result["type"] == "python"


# ═══════════════════════════════════════════════════════════════════════════
# resolve_sandbox
# ═══════════════════════════════════════════════════════════════════════════


_FAKE_INDEX = """
sandboxes[1]:
  {name: "mybox", path: "/home/max/Development/mybox", budget_max: 5000, skills_count: 0, status: "idle", last_seen: "2026-06-09T12:00:00"}
version: "1.0.0"
"""


class TestResolveSandbox:
    """Sandbox path resolution: INDEX.toon → literal path → ~/Development/."""

    def test_from_index_toon(self, tmp_path: Path) -> None:
        """When INDEX.toon has an entry, use its path."""
        index_file = tmp_path / "INDEX.toon"
        target = tmp_path / "mybox"
        target.mkdir()
        index_file.write_text(
            f'{{name: "mybox", path: "{target}", budget_max: 5000,'
            f' skills_count: 0, status: "idle", last_seen: "2026-01-01T00:00:00"}}'
        )
        with patch("hero.core.project.INDEX_PATH", index_file):
            assert resolve_sandbox("mybox") == target.resolve()

    def test_literal_path(self, tmp_path: Path) -> None:
        """A literal path that exists on disk resolves directly."""
        result = resolve_sandbox(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_development_fallback(self, tmp_path: Path) -> None:
        """When nothing matches, try ~/Development/<name>."""
        fake_dev = tmp_path / "Development"
        fake_dev.mkdir()
        target = fake_dev / "myapp"
        target.mkdir()
        with patch("hero.core.project.INDEX_PATH", tmp_path / "nonexistent"):
            with patch("hero.core.project.DEVELOPMENT_DIR", fake_dev):
                assert resolve_sandbox("myapp") == target.resolve()

    def test_not_found_raises(self, tmp_path: Path) -> None:
        """A name that matches nothing raises FileNotFoundError."""
        with patch("hero.core.project.INDEX_PATH", tmp_path / "no_index"):
            with pytest.raises(FileNotFoundError, match="not found"):
                resolve_sandbox("nonexistent_sandbox_xyz")

    def test_index_wins_over_literal(self, tmp_path: Path) -> None:
        """INDEX.toon path takes priority over a matching literal path."""
        index_file = tmp_path / "INDEX.toon"
        index_target = tmp_path / "index_target"
        index_target.mkdir()
        index_file.write_text(
            f'{{name: "testbox", path: "{index_target}", budget_max: 5000,'
            f' skills_count: 0, status: "idle", last_seen: "2026-01-01T00:00:00"}}'
        )
        literal_target = tmp_path / "testbox"
        literal_target.mkdir()
        with patch("hero.core.project.INDEX_PATH", index_file):
            result = resolve_sandbox("testbox")
            assert result == index_target.resolve()


# ═══════════════════════════════════════════════════════════════════════════
# _parse_index_toon
# ═══════════════════════════════════════════════════════════════════════════


class TestParseIndexToon:
    """INDEX.toon parsing edge cases."""

    def test_empty_file(self, tmp_path: Path) -> None:
        index = tmp_path / "INDEX.toon"
        index.write_text("")
        with patch("hero.core.project.INDEX_PATH", index):
            assert _parse_index_toon() == {}

    def test_no_entries(self, tmp_path: Path) -> None:
        index = tmp_path / "INDEX.toon"
        index.write_text("sandboxes[0]:\nversion: \"1.0\"\n")
        with patch("hero.core.project.INDEX_PATH", index):
            assert _parse_index_toon() == {}

    def test_multiple_entries(self, tmp_path: Path) -> None:
        index = tmp_path / "INDEX.toon"
        index.write_text(
            'sandboxes[3]:\n'
            '  {name: "a", path: "/tmp/a", budget_max: 1000, skills_count: 0, status: "idle", last_seen: "2026-01-01T00:00:00"}\n'
            '  {name: "b", path: "/tmp/b", budget_max: 2000, skills_count: 1, status: "active", last_seen: "2026-06-09T00:00:00.123"}\n'
            '  {name: "c", path: "/tmp/c", budget_max: 3000, skills_count: 0, status: "new", last_seen: "2026-01-01"}\n'
            'version: "1.0.0"\n'
        )
        with patch("hero.core.project.INDEX_PATH", index):
            parsed = _parse_index_toon()
            assert parsed == {"a": "/tmp/a", "b": "/tmp/b", "c": "/tmp/c"}

    def test_no_index_file(self, tmp_path: Path) -> None:
        with patch("hero.core.project.INDEX_PATH", tmp_path / "nonexistent"):
            assert _parse_index_toon() == {}


# ═══════════════════════════════════════════════════════════════════════════
# safe_run
# ═══════════════════════════════════════════════════════════════════════════


class TestSafeRun:
    """Subprocess execution with error handling."""

    def test_successful_run(self, tmp_path: Path) -> None:
        result, err = safe_run(["echo", "hello"], cwd=tmp_path)
        assert err is None
        assert result is not None
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_command_not_found(self, tmp_path: Path) -> None:
        result, err = safe_run(["definitely_not_a_real_command_xyz"], cwd=tmp_path)
        assert result is None
        assert err is not None
        assert "not found" in err

    def test_timeout(self, tmp_path: Path) -> None:
        """A command that sleeps too long should hit the timeout."""
        result, err = safe_run(["sleep", "5"], cwd=tmp_path, timeout=1)
        assert result is None
        assert err is not None
        assert "timed out" in err

    def test_nonzero_exit_is_not_an_error(self, tmp_path: Path) -> None:
        """safe_run only catches *infrastructure* errors, not non-zero exits."""
        if (tmp_path / "nonexistent_dir").exists():
            (tmp_path / "nonexistent_dir").rmdir()
        result, err = safe_run(["ls", str(tmp_path / "nonexistent_dir")], cwd=tmp_path)
        # `ls` on a non-existent path returns non-zero, but subprocess itself succeeded
        assert err is None
        assert result is not None
        assert result.returncode != 0

    def test_generic_exception(self, tmp_path: Path) -> None:
        """Generic exceptions are caught and returned as error strings."""
        with patch("subprocess.run", side_effect=OSError("disk full")):
            result, err = safe_run(["echo", "hi"], cwd=tmp_path)
            assert result is None
            assert err == "disk full"
