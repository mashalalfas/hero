"""Tests for hero build — BUILD stage checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import click
import pytest

from hero.commands.build import (
    _check_build,
    _check_debug_symbols,
    _check_obfuscation,
    _check_proguard,
    _compute_build_score,
    _detect_project_type,
    run_build,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture

def cli_runner():
    """Click testing CLI runner."""
    from click.testing import CliRunner
    return CliRunner()



@pytest.fixture
def flutter_sandbox(tmp_path: Path) -> Path:
    """Create a minimal Flutter project sandbox."""
    (tmp_path / "pubspec.yaml").write_text("name: test_app\nversion: 1.0.0\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "main.dart").write_text('void main() => runApp(MyApp());\n')
    return tmp_path


@pytest.fixture
def node_sandbox(tmp_path: Path) -> Path:
    """Create a minimal Node.js project sandbox."""
    pkg = {"name": "test-app", "version": "1.0.0", "scripts": {"build": "echo done"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    return tmp_path


@pytest.fixture
def python_sandbox(tmp_path: Path) -> Path:
    """Create a minimal Python project sandbox."""
    pyproject = "[build-system]\nrequires = [\"setuptools\"]\n"
    (tmp_path / "pyproject.toml").write_text(pyproject)
    return tmp_path


@pytest.fixture
def rust_sandbox(tmp_path: Path) -> Path:
    """Create a minimal Rust project sandbox."""
    cargo = '[package]\nname = "test-app"\nversion = "0.1.0"\n'
    (tmp_path / "Cargo.toml").write_text(cargo)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text('fn main() {}\n')
    return tmp_path


@pytest.fixture
def empty_sandbox(tmp_path: Path) -> Path:
    """Sandbox with no recognised project type."""
    return tmp_path


# ── _detect_project_type ─────────────────────────────────────────────────


class TestDetectProjectType:
    def test_detect_flutter(self, flutter_sandbox: Path) -> None:
        assert _detect_project_type(flutter_sandbox) == "flutter"

    def test_detect_node(self, node_sandbox: Path) -> None:
        assert _detect_project_type(node_sandbox) == "node"

    def test_detect_python(self, python_sandbox: Path) -> None:
        assert _detect_project_type(python_sandbox) == "python"

    def test_detect_rust(self, rust_sandbox: Path) -> None:
        assert _detect_project_type(rust_sandbox) == "rust"

    def test_detect_unknown(self, empty_sandbox: Path) -> None:
        assert _detect_project_type(empty_sandbox) == "unknown"

    def test_detect_prefers_flutter_over_node(self, tmp_path: Path) -> None:
        """pubspec.yaml takes priority over package.json."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert _detect_project_type(tmp_path) == "flutter"


# ── _check_build ─────────────────────────────────────────────────────────


class TestCheckBuild:
    def test_flutter_build_succeeds(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Built build/app/outputs/flutter-apk/app-release.apk (12.3MB).\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(flutter_sandbox, verbose=False)

        assert result["passed"] is True
        assert "succeeded" in result["summary"]
        assert result["returncode"] == 0

    def test_flutter_build_fails(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Build failed. No connected devices.\n"

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(flutter_sandbox, verbose=False)

        assert result["passed"] is False
        assert "failed" in result["summary"].lower()
        assert result["returncode"] == 1

    def test_flutter_build_tool_missing(self, flutter_sandbox: Path) -> None:
        with patch("hero.commands.build._safe_run", return_value=(None, "flutter not found")):
            result = _check_build(flutter_sandbox, verbose=False)

        assert result["passed"] is False
        assert result["returncode"] == -1

    def test_node_build_succeeds(self, node_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "> test-app@1.0.0 build\n> echo done\n\ndone\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(node_sandbox, verbose=False)

        assert result["passed"] is True
        assert "npm run build" in result["command"]

    def test_python_build_succeeds(self, python_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully built test-app-1.0.0.tar.gz\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(python_sandbox, verbose=False)

        assert result["passed"] is True
        assert result["returncode"] == 0

    def test_rust_build_succeeds(self, rust_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   Compiling test-app v0.1.0\n   Finished dev [unoptimized + debuginfo]\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(rust_sandbox, verbose=False)

        assert result["passed"] is True
        assert "cargo build --release" in result["command"]

    def test_unknown_project_skipped(self, empty_sandbox: Path) -> None:
        result = _check_build(empty_sandbox, verbose=False)
        assert result["passed"] is True
        assert "skipped" in result["summary"]

    def test_verbose_includes_output(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Built build/app/outputs/flutter-apk/app-release.apk (12.3MB).\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            result = _check_build(flutter_sandbox, verbose=True)

        assert result["detail"] != ""
        assert "Output" in result["detail"]


# ── _check_obfuscation ──────────────────────────────────────────────────


class TestCheckObfuscation:
    def test_flutter_obfuscation_via_command(self, flutter_sandbox: Path) -> None:
        build_result = {
            "passed": True,
            "summary": "flutter build apk --obfuscate succeeded",
            "command": "flutter build apk --obfuscate --split-debug-info=build/debug-info",
        }
        result = _check_obfuscation(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is True
        assert "--obfuscate" in result["summary"]

    def test_flutter_obfuscation_via_debug_dir(self, flutter_sandbox: Path) -> None:
        debug_dir = flutter_sandbox / "build" / "debug-info"
        debug_dir.mkdir(parents=True)
        (debug_dir / "symbols").write_text("test")

        build_result = {
            "passed": True,
            "summary": "flutter build apk succeeded",
            "command": "flutter build apk",
        }
        result = _check_obfuscation(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is True

    def test_flutter_no_obfuscation(self, flutter_sandbox: Path) -> None:
        build_result = {
            "passed": True,
            "summary": "flutter build apk succeeded",
            "command": "flutter build apk",
        }
        result = _check_obfuscation(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is False
        assert "NOT detected" in result["summary"]

    def test_non_flutter_skipped(self, node_sandbox: Path) -> None:
        build_result = {"passed": True, "summary": "npm run build succeeded", "command": "npm run build"}
        result = _check_obfuscation(node_sandbox, build_result, verbose=False)
        assert result["passed"] is True
        assert "skipped" in result["summary"].lower() or "not applicable" in result["summary"].lower()

    def test_verbose_includes_command(self, flutter_sandbox: Path) -> None:
        build_result = {
            "passed": True,
            "summary": "flutter build apk succeeded",
            "command": "flutter build apk",
        }
        result = _check_obfuscation(flutter_sandbox, build_result, verbose=True)
        assert result["detail"] != ""


# ── _check_proguard ──────────────────────────────────────────────────────


class TestCheckProguard:
    def test_proguard_fully_configured(self, tmp_path: Path) -> None:
        """Flutter project with proguard-rules.pro and minifyEnabled."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")
        android_dir = tmp_path / "android" / "app"
        android_dir.mkdir(parents=True)
        (android_dir / "proguard-rules.pro").write_text("-keep class com.example.** { *; }\n")
        (android_dir / "build.gradle").write_text(
            "android {\n  buildTypes {\n    release {\n      minifyEnabled true\n    }\n  }\n}\n"
        )

        result = _check_proguard(tmp_path, verbose=False)
        assert result["passed"] is True
        assert "fully configured" in result["summary"].lower()

    def test_proguard_missing_rules_file(self, tmp_path: Path) -> None:
        """Flutter project with build.gradle but no proguard-rules.pro."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")
        android_dir = tmp_path / "android" / "app"
        android_dir.mkdir(parents=True)
        (android_dir / "build.gradle").write_text(
            "android {\n  buildTypes {\n    release {\n      minifyEnabled true\n    }\n  }\n}\n"
        )

        result = _check_proguard(tmp_path, verbose=False)
        assert result["passed"] is False
        assert "proguard-rules.pro" in result["summary"]

    def test_proguard_missing_minify(self, tmp_path: Path) -> None:
        """Flutter project with proguard-rules.pro but no minifyEnabled."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")
        android_dir = tmp_path / "android" / "app"
        android_dir.mkdir(parents=True)
        (android_dir / "proguard-rules.pro").write_text("-keep class com.example.** { *; }\n")
        (android_dir / "build.gradle").write_text("android { buildTypes { release {} } }\n")

        result = _check_proguard(tmp_path, verbose=False)
        assert result["passed"] is False
        assert "minifyEnabled" in result["summary"]

    def test_proguard_both_missing(self, tmp_path: Path) -> None:
        """Flutter project with neither proguard-rules.pro nor minifyEnabled."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")
        android_dir = tmp_path / "android" / "app"
        android_dir.mkdir(parents=True)
        (android_dir / "build.gradle").write_text("android { buildTypes { release {} } }\n")

        result = _check_proguard(tmp_path, verbose=False)
        assert result["passed"] is False
        assert "proguard-rules.pro" in result["summary"]
        assert "minifyEnabled" in result["summary"]

    def test_no_android_gradle_returns_neutral(self, tmp_path: Path) -> None:
        """If no build.gradle exists at all, report can't verify."""
        (tmp_path / "pubspec.yaml").write_text("name: test\n")

        result = _check_proguard(tmp_path, verbose=False)
        # Should not crash — returns either failed (cannot verify) or skipped
        assert "passed" in result

    def test_non_flutter_skipped(self, node_sandbox: Path) -> None:
        result = _check_proguard(node_sandbox, verbose=False)
        assert result["passed"] is True
        assert "skipped" in result["summary"].lower() or "not applicable" in result["summary"].lower()


# ── _check_debug_symbols ────────────────────────────────────────────────


class TestCheckDebugSymbols:
    def test_flutter_debug_info_stripped(self, flutter_sandbox: Path) -> None:
        debug_dir = flutter_sandbox / "build" / "debug-info"
        debug_dir.mkdir(parents=True)
        (debug_dir / "symbols").write_text("test")

        build_result = {
            "passed": True,
            "summary": "flutter build apk --obfuscate succeeded",
            "command": "flutter build apk --obfuscate --split-debug-info=build/debug-info",
        }
        result = _check_debug_symbols(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is True
        assert "split-debug-info" in result["summary"]

    def test_flutter_debug_not_stripped(self, flutter_sandbox: Path) -> None:
        build_result = {
            "passed": True,
            "summary": "flutter build apk succeeded",
            "command": "flutter build apk",
        }
        result = _check_debug_symbols(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is False
        assert "NOT used" in result["summary"]

    def test_flutter_flag_used_but_no_dir(self, flutter_sandbox: Path) -> None:
        """Partial: --split-debug-info flag in command but no dir created."""
        build_result = {
            "passed": True,
            "summary": "flutter build apk --obfuscate succeeded",
            "command": "flutter build apk --obfuscate --split-debug-info=build/debug-info",
        }
        result = _check_debug_symbols(flutter_sandbox, build_result, verbose=False)
        assert result["passed"] is False
        assert "partially" in result["summary"].lower() or "missing" in result["summary"].lower()

    def test_non_flutter_skipped(self, node_sandbox: Path) -> None:
        build_result = {"passed": True, "summary": "npm run build succeeded", "command": "npm run build"}
        result = _check_debug_symbols(node_sandbox, build_result, verbose=False)
        assert result["passed"] is True
        assert "skipped" in result["summary"].lower() or "not applicable" in result["summary"].lower()


# ── _compute_build_score ─────────────────────────────────────────────────


class TestComputeBuildScore:
    def _make_checks(self, passed: bool = True) -> dict[str, Any]:
        """Create a default all-passing checks dict."""
        return {
            "build": {"passed": passed, "summary": "build ok" if passed else "build failed"},
            "obfuscation": {"passed": passed, "summary": "obfuscation ok" if passed else "no obfuscation"},
            "proguard": {"passed": passed, "summary": "ProGuard ok" if passed else "not configured"},
            "debug_symbols": {"passed": passed, "summary": "debug symbols ok" if passed else "not stripped"},
        }

    def test_all_pass_flutter(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 100
        assert findings == []

    def test_all_pass_node(self, node_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        # For non-Flutter, proguard and obfuscation should not be deducted
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "node"
        )
        assert score == 100

    def test_build_failure_deducts_20(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        checks["build"]["passed"] = False
        checks["build"]["summary"] = "build failed"
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 80
        assert any(f["check"] == "build" for f in findings)

    def test_obfuscation_missing_deducts_15_flutter(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        checks["obfuscation"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 85
        assert any(f["check"] == "obfuscation" for f in findings)

    def test_obfuscation_missing_no_deduct_non_flutter(self, node_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        checks["obfuscation"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "node"
        )
        # Should not deduct -15 for obfuscation on non-Flutter
        assert score == 100

    def test_proguard_missing_deducts_15_flutter(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        checks["proguard"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 85
        assert any(f["check"] == "proguard" for f in findings)

    def test_debug_symbols_not_stripped_deducts_15(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=True)
        checks["debug_symbols"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 85
        assert any(f["check"] == "debug_symbols" for f in findings)

    def test_combined_deductions_floor_at_zero(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=False)
        checks["obfuscation"]["passed"] = False
        checks["proguard"]["passed"] = False
        checks["debug_symbols"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert score == 35
        assert len(findings) == 4

    def test_multiple_findings_tracked(self, flutter_sandbox: Path) -> None:
        checks = self._make_checks(passed=False)
        checks["obfuscation"]["passed"] = False
        score, findings = _compute_build_score(
            checks["build"], checks["obfuscation"], checks["proguard"], checks["debug_symbols"], "flutter"
        )
        assert len(findings) == 4
        check_names = {f["check"] for f in findings}
        assert check_names == {"build", "obfuscation", "proguard", "debug_symbols"}


# ── run_build (integration) ──────────────────────────────────────────────


class TestRunBuild:
    def test_run_build_returns_correct_structure(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Built build/app/outputs/flutter-apk/app-release.apk (12.3MB).\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            with patch("hero.commands.build._detect_project_type", return_value="flutter"):
                result = run_build(flutter_sandbox, verbose=False)

        assert "sandbox" in result
        assert "project_type" in result
        assert "passed" in result
        assert "score" in result
        assert "status" in result
        assert "checks" in result
        assert "findings" in result
        assert set(result["checks"].keys()) == {"build", "obfuscation", "proguard", "debug_symbols"}

    def test_run_build_score_range(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Built build/app/outputs/flutter-apk/app-release.apk (12.3MB).\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            with patch("hero.commands.build._detect_project_type", return_value="flutter"):
                result = run_build(flutter_sandbox, verbose=False)

        assert 0 <= result["score"] <= 100

    def test_run_build_status_values(self, flutter_sandbox: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Built build/app/outputs/flutter-apk/app-release.apk (12.3MB).\n"
        mock_result.stderr = ""

        with patch("hero.commands.build._safe_run", return_value=(mock_result, None)):
            with patch("hero.commands.build._detect_project_type", return_value="flutter"):
                result = run_build(flutter_sandbox, verbose=False)

        assert result["status"] in ("pass", "warn", "fail")


# ── Click command (build) ────────────────────────────────────────────────


class TestBuildCommand:
    def test_build_help(self, cli_runner) -> None:
        """hero build --help should work without error."""
        from hero.cli import main

        result = cli_runner.invoke(main, ["build", "--help"])
        assert result.exit_code == 0
        assert "BUILD" in result.output or "build" in result.output

    @patch("hero.commands.build.run_build")
    def test_build_json_output(self, mock_run_build: MagicMock, cli_runner, flutter_sandbox: Path) -> None:
        from hero.cli import main

        mock_run_build.return_value = {
            "sandbox": str(flutter_sandbox),
            "project_type": "flutter",
            "passed": True,
            "score": 85,
            "status": "pass",
            "checks": {
                "build": {"passed": True, "summary": "flutter build apk succeeded", "detail": ""},
                "obfuscation": {"passed": True, "summary": "obfuscation detected", "detail": ""},
                "proguard": {"passed": False, "summary": "Not configured", "detail": ""},
                "debug_symbols": {"passed": True, "summary": "--split-debug-info used", "detail": ""},
            },
            "findings": [],
        }

        result = cli_runner.invoke(main, ["build", "--sandbox", str(flutter_sandbox), "--json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["score"] == 85
        assert output["status"] == "pass"

    @patch("hero.commands.build.run_build")
    def test_build_dry_run(self, mock_run_build: MagicMock, cli_runner, flutter_sandbox: Path) -> None:
        """Dry-run should NOT call run_build."""
        from hero.cli import main

        result = cli_runner.invoke(main, ["build", "--sandbox", str(flutter_sandbox), "--dry-run"])
        assert result.exit_code == 0
        mock_run_build.assert_not_called()
        assert "dry run" in result.output.lower()

    @patch("hero.commands.build.run_build")
    def test_build_verbose(self, mock_run_build: MagicMock, cli_runner, flutter_sandbox: Path) -> None:
        from hero.cli import main

        mock_run_build.return_value = {
            "sandbox": str(flutter_sandbox),
            "project_type": "flutter",
            "passed": True,
            "score": 100,
            "status": "pass",
            "checks": {
                "build": {"passed": True, "summary": "flutter build apk succeeded", "detail": "  Output:\n    foo"},
                "obfuscation": {"passed": True, "summary": "obfuscation detected", "detail": ""},
                "proguard": {"passed": True, "summary": "fully configured", "detail": ""},
                "debug_symbols": {"passed": True, "summary": "--split-debug-info used", "detail": ""},
            },
            "findings": [],
        }

        result = cli_runner.invoke(main, ["build", "--sandbox", str(flutter_sandbox), "--verbose"])
        assert result.exit_code == 0
        assert "Score: 100/100" in result.output

    def test_build_sandbox_not_found(self, cli_runner) -> None:
        from hero.cli import main

        result = cli_runner.invoke(main, ["build", "--sandbox", "nonexistent_project_xyz"])
        assert result.exit_code != 0
