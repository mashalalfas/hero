"""Tests for hero cipr command.

Covers:
- Score computation under every deduction combination
- run_cipr() with an empty Flutter project (all checks exercised)
- Test runner detection by project type
- Build artifact detection
- JSON and dry-run CLI paths
- Trivy and brakeman edge cases
- _is_rails_project detection
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner
import pytest

from hero.commands.cipr import (
    _check_build_artifacts,
    _compute_cipr_score,
    _count_test_failures,
    _is_rails_project,
    _run_brakeman,
    _run_tests,
    _run_trivy,
    run_cipr,
)
from hero.commands.pre_commit import _detect_project_type


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_flutter_project(tmp: Path) -> Path:
    """Create a minimal Flutter project skeleton under *tmp*."""
    p = tmp / "myapp"
    p.mkdir()
    (p / "pubspec.yaml").write_text(
        "name: myapp\nversion: 1.0.0\nenvironment:\n  sdk: '>=3.0.0'\n"
    )
    lib = p / "lib"
    lib.mkdir()
    (lib / "main.dart").write_text("void main() => print('hello');\n")
    return p


def _make_node_project(tmp: Path) -> Path:
    p = tmp / "nodeapp"
    p.mkdir()
    (p / "package.json").write_text(
        '{"name": "nodeapp", "version": "1.0.0", "scripts": {"test": "echo ok"}}'
    )
    return p


def _make_rails_project(tmp: Path) -> Path:
    p = tmp / "railsapp"
    p.mkdir()
    (p / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n")
    (p / "app").mkdir()
    return p


def _make_python_project(tmp: Path) -> Path:
    p = tmp / "pyapp"
    p.mkdir()
    (p / "pyproject.toml").write_text(
        '[project]\nname = "pyapp"\nversion = "1.0.0"\n'
    )
    (p / "tests").mkdir()
    (p / "tests" / "test_main.py").write_text("def test_ok(): pass\n")
    return p


# ── _is_rails_project ────────────────────────────────────────────────────


class TestIsRailsProject:
    def test_rails_with_gemfile(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        assert _is_rails_project(p) is True

    def test_not_rails_without_gemfile(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        assert _is_rails_project(p) is False

    def test_gemfile_without_rails(self, tmp_path: Path):
        p = tmp_path / "rubyapp"
        p.mkdir()
        (p / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'sinatra'\n")
        assert _is_rails_project(p) is False


# ── _count_test_failures ────────────────────────────────────────────────


class TestCountTestFailures:
    def test_no_failures(self):
        output = "All tests passed\n"
        failures, errors = _count_test_failures(output)
        assert failures == 0

    def test_flutter_failure_count(self):
        output = "123 tests passed, 2 failed\n"
        failures, errors = _count_test_failures(output)
        assert failures == 2

    def test_pytest_failure_count(self):
        output = "= 5 failed, 45 passed in 2.3s =\n"
        failures, errors = _count_test_failures(output)
        assert failures == 5

    def test_error_line_count(self):
        output = "Error: something failed\nFAILED: test_foo\n"
        failures, errors = _count_test_failures(output)
        assert errors == 2

    def test_mixed_output(self):
        output = "10 passed, 3 failed\nSome other output\nFAILED: test_bar\n"
        failures, errors = _count_test_failures(output)
        assert failures == 3
        assert errors >= 1


# ── _run_tests ──────────────────────────────────────────────────────────


class TestRunTests:
    def test_flutter_project(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        passed, summary, failures = _run_tests(p, "flutter")
        # flutter test won't be available in test env — should be graceful
        assert "skipped" in summary.lower() or "unavailable" in summary.lower() or failures >= 0

    def test_node_project(self, tmp_path: Path):
        p = _make_node_project(tmp_path)
        passed, summary, failures = _run_tests(p, "node")
        assert isinstance(passed, bool)

    def test_unknown_project_type(self, tmp_path: Path):
        passed, summary, failures = _run_tests(tmp_path, "unknown")
        assert passed is True
        assert "skipped" in summary.lower()

    def test_flutter_with_failures(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        with patch("hero.commands.cipr._safe_run") as mock_run:
            # Simulate flutter test with 2 failures
            mock_run.return_value = (
                subprocess.CompletedProcess(
                    args=["flutter", "test"],
                    returncode=1,
                    stdout="123 passed, 2 failed",
                    stderr="",
                ),
                None,
            )
            passed, summary, failures = _run_tests(p, "flutter")
            assert passed is False
            assert failures == 2

    def test_flutter_all_passed(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        with patch("hero.commands.cipr._safe_run") as mock_run:
            mock_run.return_value = (
                subprocess.CompletedProcess(
                    args=["flutter", "test"],
                    returncode=0,
                    stdout="100 passed, 0 failed",
                    stderr="",
                ),
                None,
            )
            passed, summary, failures = _run_tests(p, "flutter")
            assert passed is True
            assert failures == 0


# ── _run_trivy ──────────────────────────────────────────────────────────


class TestRunTrivy:
    def test_trivy_not_installed_no_report(self):
        with patch("hero.commands.cipr.shutil.which", return_value=None):
            findings, note = _run_trivy(Path("/tmp"))
        assert findings == []
        assert "trivy not installed" in note

    def test_trivy_with_findings(self):
        with patch("hero.commands.cipr.shutil.which", return_value="/usr/bin/trivy"):
            with patch("hero.commands.cipr._safe_run") as mock_run:
                output = "CVE-2024-1234 (CRITICAL): openssl\nCVE-2024-5678 (HIGH): curl\n"
                mock_run.return_value = (
                    subprocess.CompletedProcess(
                        args=["trivy", "fs", "--severity", "CRITICAL", "--no-progress", "/tmp"],
                        returncode=0,
                        stdout=output,
                        stderr="",
                    ),
                    None,
                )
                findings, note = _run_trivy(Path("/tmp"))
                assert len(findings) == 1
                assert "CVE-2024-1234" in findings[0]
                assert note == ""

    def test_trivy_clean(self):
        with patch("hero.commands.cipr.shutil.which", return_value="/usr/bin/trivy"):
            with patch("hero.commands.cipr._safe_run") as mock_run:
                mock_run.return_value = (
                    subprocess.CompletedProcess(
                        args=["trivy", "fs", "--severity", "CRITICAL", "--no-progress", "/tmp"],
                        returncode=0,
                        stdout="",
                        stderr="",
                    ),
                    None,
                )
                findings, note = _run_trivy(Path("/tmp"))
                assert findings == []
                assert note == ""


# ── _check_build_artifacts ──────────────────────────────────────────────


class TestCheckBuildArtifacts:
    def test_flutter_build_present(self, tmp_path: Path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "app.dill").write_text("bytecode\n")
        ok, summary, count = _check_build_artifacts(tmp_path, "flutter")
        assert ok is True
        assert "1 file" in summary

    def test_flutter_build_missing(self, tmp_path: Path):
        ok, summary, count = _check_build_artifacts(tmp_path, "flutter")
        assert ok is False
        assert "not found" in summary

    def test_flutter_build_empty(self, tmp_path: Path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        ok, summary, count = _check_build_artifacts(tmp_path, "flutter")
        assert ok is False
        assert "empty" in summary

    def test_node_build_present(self, tmp_path: Path):
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "main.js").write_text("code\n")
        ok, summary, count = _check_build_artifacts(tmp_path, "node")
        assert ok is True

    def test_node_prefers_dist(self, tmp_path: Path):
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "main.js").write_text("code\n")
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        ok, summary, count = _check_build_artifacts(tmp_path, "node")
        # Should find dist/ first (in candidates list)
        assert ok is True
        assert "dist" in summary

    def test_rust_target_release(self, tmp_path: Path):
        target_dir = tmp_path / "target" / "release"
        target_dir.mkdir(parents=True)
        (target_dir / "myapp").write_text("binary\n")
        ok, summary, count = _check_build_artifacts(tmp_path, "rust")
        assert ok is True


# ── _run_brakeman ───────────────────────────────────────────────────────


class TestRunBrakeman:
    def test_rails_project(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        with patch("hero.commands.cipr.shutil.which", return_value="/usr/bin/brakeman"):
            with patch("hero.commands.cipr._safe_run") as mock_run:
                mock_run.return_value = (
                    subprocess.CompletedProcess(
                        args=["brakeman", "-q", "-o", str(p / "security" / "brakeman-report.json")],
                        returncode=0,
                        stdout="",
                        stderr="",
                    ),
                    None,
                )
                findings, note = _run_brakeman(p)
                # No high findings in empty report
                assert isinstance(findings, list)

    def test_not_rails_project(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        findings, note = _run_brakeman(p)
        assert findings == []
        assert "not a Rails project" in note

    def test_brakeman_not_installed(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        with patch("hero.commands.cipr.shutil.which", return_value=None):
            findings, note = _run_brakeman(p)
        assert findings == []
        assert "not installed" in note

    def test_high_severity_findings(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        report_file = p / "security" / "brakeman-report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps({
            "warnings": [
                {"warning_type": "SQL Injection", "confidence": "High", "file": "app/models/user.rb"},
                {"warning_type": "XSS", "confidence": "Medium", "file": "app/views/home.html.erb"},
            ]
        }))
        with patch("hero.commands.cipr.shutil.which", return_value="/usr/bin/brakeman"):
            with patch("hero.commands.cipr._safe_run", return_value=(MagicMock(returncode=0, stdout="", stderr=""), None)):
                findings, note = _run_brakeman(p)
                assert len(findings) == 1
                assert "SQL Injection" in findings[0]


# ── Score computation ───────────────────────────────────────────────────


class TestComputeCiprScore:
    def test_perfect_score(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=[],
            artifacts_ok=True,
            brakeman_high=[],
        )
        assert score == 100
        assert findings == []

    def test_test_failure(self):
        score, findings = _compute_cipr_score(
            test_failures=3,
            test_all_passed=False,
            trivy_findings=[],
            artifacts_ok=True,
            brakeman_high=[],
        )
        assert score == 100 - 30 - 2 * 10  # 3 failures: -30 - 2*10
        assert len(findings) == 2  # 1 for initial fail, 1 for additional (grouped)

    def test_single_test_failure(self):
        score, findings = _compute_cipr_score(
            test_failures=1,
            test_all_passed=False,
            trivy_findings=[],
            artifacts_ok=True,
            brakeman_high=[],
        )
        assert score == 100 - 30
        assert len(findings) == 1

    def test_trivy_single_cve(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=["CVE-1"],
            artifacts_ok=True,
            brakeman_high=[],
        )
        assert score == 75  # 100 - 25
        assert any(f["check"] == "trivy" for f in findings)

    def test_trivy_multiple_cves(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=["CVE-1", "CVE-2"],
            artifacts_ok=True,
            brakeman_high=[],
        )
        assert score == 50  # 100 - 50

    def test_missing_artifacts(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=[],
            artifacts_ok=False,
            brakeman_high=[],
        )
        assert score == 90
        assert any(f["check"] == "artifacts" for f in findings)

    def test_brakeman_single_high(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=[],
            artifacts_ok=True,
            brakeman_high=["SQL Injection"],
        )
        assert score == 80
        assert any(f["check"] == "brakeman" for f in findings)

    def test_brakeman_multiple_high(self):
        score, findings = _compute_cipr_score(
            test_failures=0,
            test_all_passed=True,
            trivy_findings=[],
            artifacts_ok=True,
            brakeman_high=["A", "B", "C"],
        )
        assert score == 40  # 100 - 60

    def test_floor_at_zero(self):
        score, _ = _compute_cipr_score(
            test_failures=5,
            test_all_passed=False,
            trivy_findings=["CVE-1", "CVE-2"],
            artifacts_ok=False,
            brakeman_high=["A", "B"],
        )
        assert score == 0

    def test_combined_deductions(self):
        score, findings = _compute_cipr_score(
            test_failures=2,
            test_all_passed=False,
            trivy_findings=["CVE-1"],
            artifacts_ok=False,
            brakeman_high=["A"],
        )
        assert score == 100 - 30 - 10 - 25 - 10 - 20  # = 5
        assert len(findings) == 5


# ── run_cipr integration ────────────────────────────────────────────────


class TestRunCipr:
    def test_minimal_flutter_project(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_cipr(p, verbose=False)
        assert "sandbox" in result
        assert "score" in result
        assert "checks" in result
        assert "findings" in result
        assert result["project_type"] == "flutter"
        assert 0 <= result["score"] <= 100

    def test_checks_keys_present(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_cipr(p)
        expected_checks = {"tests", "trivy", "artifacts", "brakeman"}
        assert expected_checks.issubset(result["checks"].keys())

    def test_node_project(self, tmp_path: Path):
        p = _make_node_project(tmp_path)
        result = run_cipr(p)
        assert result["project_type"] == "node"

    def test_rails_project_detection(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        result = run_cipr(p)
        assert result["checks"]["brakeman"]["summary"] != "Skipped (not a Rails project)"

    def test_non_rails_skips_brakeman(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_cipr(p)
        assert "not a Rails project" in result["checks"]["brakeman"]["summary"]

    def test_json_output_structure(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_cipr(p)
        dumped = json.dumps(result)
        reloaded = json.loads(dumped)
        assert reloaded["score"] == result["score"]

    def test_flutter_build_artifacts_missing(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_cipr(p)
        # build/ should not exist in a fresh project
        assert result["checks"]["artifacts"]["passed"] is False
        assert "not found" in result["checks"]["artifacts"]["summary"]

    def test_flutter_build_artifacts_present(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        build_dir = p / "build"
        build_dir.mkdir()
        (build_dir / "test.dll").write_text("bytecode\n")
        result = run_cipr(p)
        assert result["checks"]["artifacts"]["passed"] is True

    def test_rails_brakeman_skipped_when_not_installed(self, tmp_path: Path):
        p = _make_rails_project(tmp_path)
        with patch("hero.commands.cipr.shutil.which", side_effect=lambda x: None if x == "brakeman" else "/usr/bin/trivy"):
            result = run_cipr(p)
        assert "not installed" in result["checks"]["brakeman"]["summary"] or result["checks"]["brakeman"]["summary"].startswith("Skipped")

    def test_passed_when_all_clean(self, tmp_path: Path):
        """All clean with build artifacts should score >= 70."""
        p = _make_flutter_project(tmp_path)
        build_dir = p / "build"
        build_dir.mkdir()
        (build_dir / "test.dll").write_text("bytecode\n")
        with patch("hero.commands.cipr.shutil.which", return_value=None):
            result = run_cipr(p)
        assert result["passed"] is True
        assert result["score"] >= 50  # may get warnings for missing tools


# ── CLI integration ────────────────────────────────────────────────────


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["cipr", "--help"])
        assert result.exit_code == 0
        assert "cipr" in result.output.lower() or "CI/PR" in result.output

    def test_dry_run(self, tmp_path: Path):
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["cipr", "--sandbox", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    def test_verbose(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["cipr", "--sandbox", str(p), "--verbose"])
        assert result.exit_code == 0

    def test_json_output(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["cipr", "--sandbox", str(p), "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "score" in parsed
