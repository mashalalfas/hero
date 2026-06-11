"""Tests for hero score command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hero.commands.score import (
    _detect_project_type,
    _resolve_sandbox,
    _score_verify,
    _scan_secrets_fallback,
    _count_copyright_headers,
    score,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal flutter-like project for testing."""
    (tmp_path / "pubspec.yaml").write_text("name: test_app\nversion: 1.0.0\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "main.dart").write_text(
        '// Copyright 2024 Test\nvoid main() {}\n'
    )
    return tmp_path


# ── Helpers ─────────────────────────────────────────────────────────────

class TestResolveSandbox:
    def test_named_sandbox(self, tmp_path: Path):
        with patch("hero.commands.score.SANDBOX_DIR", tmp_path):
            sandbox_dir = tmp_path / "mybox"
            sandbox_dir.mkdir()
            result = _resolve_sandbox("mybox")
            assert result == sandbox_dir

    def test_direct_path(self, tmp_path: Path):
        result = _resolve_sandbox(str(tmp_path))
        assert result == tmp_path

    def test_development_fallback(self, tmp_path: Path):
        fake_dev = tmp_path / "Development"
        fake_dev.mkdir()
        target = fake_dev / "myapp"
        target.mkdir()
        with patch("hero.commands.score.SANDBOX_DIR", tmp_path):
            with patch("hero.commands.score.Path.home", return_value=tmp_path):
                result = _resolve_sandbox("myapp")
                assert result == target

    def test_not_found_raises(self, tmp_path: Path):
        with patch("hero.commands.score.SANDBOX_DIR", tmp_path):
            with pytest.raises(Exception):  # ClickException
                _resolve_sandbox("nonexistent_sandbox_xyz")


class TestDetectProjectType:
    def test_flutter(self, tmp_path: Path):
        (tmp_path / "pubspec.yaml").write_text("")
        assert _detect_project_type(tmp_path) == "flutter"

    def test_rust(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text("")
        assert _detect_project_type(tmp_path) == "rust"

    def test_node(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}")
        assert _detect_project_type(tmp_path) == "node"

    def test_python(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("")
        assert _detect_project_type(tmp_path) == "python"

    def test_unknown(self, tmp_path: Path):
        assert _detect_project_type(tmp_path) == "unknown"


# ── Secret scan ─────────────────────────────────────────────────────────

class TestSecretScan:
    def test_clean_project(self, tmp_project: Path):
        count = _scan_secrets_fallback(tmp_project)
        assert count == 0

    def test_secret_detected(self, tmp_path: Path):
        (tmp_path / "config.yaml").write_text("api_key: AKIAIOSFODNN7EXAMPLE\n")
        count = _scan_secrets_fallback(tmp_path)
        assert count > 0

    def test_skips_node_modules(self, tmp_path: Path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "pkg.js").write_text("token = xoxb-secret-here\n")
        count = _scan_secrets_fallback(tmp_path)
        assert count == 0


# ── Copyright headers ───────────────────────────────────────────────────

class TestCopyrightHeaders:
    def test_all_present(self, tmp_path: Path):
        (tmp_path / "main.dart").write_text("// Copyright 2024\nvoid main() {}\n")
        missing, total = _count_copyright_headers(tmp_path)
        assert missing == 0

    def test_missing_header(self, tmp_path: Path):
        (tmp_path / "main.dart").write_text("void main() {}\n")
        missing, total = _count_copyright_headers(tmp_path)
        assert missing == 1

    def test_spdx_header_accepted(self, tmp_path: Path):
        (tmp_path / "main.dart").write_text("// SPDX-FileCopyrightText: 2024 Test\nvoid main() {}\n")
        missing, total = _count_copyright_headers(tmp_path)
        assert missing == 0


# ── Verify composite ────────────────────────────────────────────────────

class TestScoreVerify:
    def test_all_pass(self):
        scores = {
            "pre-commit": {"score": 95, "status": "pass", "details": "ok"},
            "build": {"score": 90, "status": "pass", "details": "ok"},
            "harden": {"score": 85, "status": "pass", "details": "ok"},
            "legal": {"score": 92, "status": "pass", "details": "ok"},
            "cipr": {"score": 88, "status": "pass", "details": "ok"},
        }
        result = _score_verify(scores)
        assert result["score"] >= 70
        assert result["status"] == "pass"

    def test_penalty_below_50(self):
        scores = {
            "pre-commit": {"score": 95, "status": "pass", "details": "ok"},
            "build": {"score": 40, "status": "fail", "details": "fail"},
            "harden": {"score": 85, "status": "pass", "details": "ok"},
            "legal": {"score": 92, "status": "pass", "details": "ok"},
            "cipr": {"score": 88, "status": "pass", "details": "ok"},
        }
        result = _score_verify(scores)
        # avg=80, -10=70 → pass (score >= 70)
        assert result["status"] == "pass"
        assert result["score"] <= 80  # penalized
        assert result["score"] >= 65  # but not by too much

    def test_penalty_below_70(self):
        scores = {
            "pre-commit": {"score": 95, "status": "pass", "details": "ok"},
            "build": {"score": 65, "status": "warn", "details": "warn"},
            "harden": {"score": 85, "status": "pass", "details": "ok"},
            "legal": {"score": 92, "status": "pass", "details": "ok"},
            "cipr": {"score": 88, "status": "pass", "details": "ok"},
        }
        result = _score_verify(scores)
        # avg ~85, -5 = 80 → pass
        assert result["status"] == "pass"


# ── CLI integration ──────────────────────────────────────────────────────

class TestCLI:
    def test_help(self, runner: CliRunner):
        result = runner.invoke(score, ["--help"])
        assert result.exit_code == 0
        assert "score" in result.output.lower() or "pipeline" in result.output.lower()

    def test_score_on_project(self, runner: CliRunner, tmp_project: Path):
        """Score a small fake flutter project."""
        result = runner.invoke(score, [
            "--pipeline", "pre-commit",
            "--sandbox", str(tmp_project),
        ])
        # Should not crash — may or may not pass depending on tooling
        assert result.exit_code == 0
        assert "pre-commit" in result.output.lower()

    def test_json_output(self, runner: CliRunner, tmp_project: Path):
        result = runner.invoke(score, [
            "--pipeline", "legal",
            "--sandbox", str(tmp_project),
            "--json",
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "scores" in parsed
        assert "legal" in parsed["scores"]

    def test_unknown_pipeline(self, runner: CliRunner, tmp_project: Path):
        result = runner.invoke(score, [
            "--pipeline", "notastage",
            "--sandbox", str(tmp_project),
        ])
        assert result.exit_code != 0

    def test_missing_sandbox(self, runner: CliRunner):
        result = runner.invoke(score, ["--pipeline", "all", "--sandbox", "/nonexistent/path/xyz"])
        assert result.exit_code != 0
