"""Tests for hero harden command.

Covers:
- Score computation under every deduction combination
- run_harden() with an empty Flutter project (all checks exercised)
- JSON and dry-run CLI paths
- _scan_secrets() with synthetic file content
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import click
from click.testing import CliRunner
import pytest

from hero.commands.harden import (
    _check_cert_pinning,
    _check_debug_symbols_stripped,
    _check_root_detection,
    _compute_harden_score,
    _scan_secrets,
    _run_trivy,
    run_harden,
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
        '{"name": "nodeapp", "version": "1.0.0", "scripts": {"build": "echo ok"}}'
    )
    return p


# ── Score computation ───────────────────────────────────────────────────


class TestComputeHardenScore:
    def test_perfect_score(self):
        score, findings = _compute_harden_score(
            trivy_findings=[],
            secret_hits=[],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 100
        assert findings == []

    def test_trivy_single_cve(self):
        score, findings = _compute_harden_score(
            trivy_findings=["CVE-1"],
            secret_hits=[],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 70
        assert len(findings) == 1
        assert findings[0]["check"] == "trivy"

    def test_trivy_capped_at_three(self):
        score, findings = _compute_harden_score(
            trivy_findings=["A", "B", "C", "D", "E"],
            secret_hits=[],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 10   # 100 - 3*30

    def test_secrets_deduction(self):
        score, _ = _compute_harden_score(
            trivy_findings=[],
            secret_hits=["key1", "key2"],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 50   # 100 - 2*25

    def test_missing_root_detection(self):
        score, findings = _compute_harden_score(
            trivy_findings=[],
            secret_hits=[],
            root_detection_found=False,
            root_note="not found",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 90
        assert any(f["check"] == "root_detection" for f in findings)

    def test_root_detection_skipped_no_deduction(self):
        """When 'skipped' is in the note no deduction should be applied."""
        score, findings = _compute_harden_score(
            trivy_findings=[],
            secret_hits=[],
            root_detection_found=False,
            root_note="skipped: not applicable",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 100
        assert not any(f["check"] == "root_detection" for f in findings)

    def test_missing_cert_pinning(self):
        score, findings = _compute_harden_score(
            trivy_findings=[],
            secret_hits=[],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=False,
            cert_note="not found",
            debug_symbols_ok=True,
            debug_note="ok",
        )
        assert score == 90
        assert any(f["check"] == "cert_pinning" for f in findings)

    def test_debug_symbols_missing(self):
        score, findings = _compute_harden_score(
            trivy_findings=[],
            secret_hits=[],
            root_detection_found=True,
            root_note="ok",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=False,
            debug_note="not stripped",
        )
        assert score == 85
        assert any(f["check"] == "debug_symbols" for f in findings)

    def test_floor_at_zero(self):
        score, _ = _compute_harden_score(
            trivy_findings=["CVE-1", "CVE-2", "CVE-3"],
            secret_hits=["s1", "s2", "s3", "s4"],
            root_detection_found=False,
            root_note="not found",
            cert_pinning_found=False,
            cert_note="not found",
            debug_symbols_ok=False,
            debug_note="not stripped",
        )
        assert score == 0

    def test_combined_deductions(self):
        score, findings = _compute_harden_score(
            trivy_findings=["CVE-1"],
            secret_hits=["s1"],
            root_detection_found=False,
            root_note="not found",
            cert_pinning_found=True,
            cert_note="ok",
            debug_symbols_ok=False,
            debug_note="not stripped",
        )
        assert score == 100 - 30 - 25 - 10 - 15  # = 20
        assert len(findings) == 4


# ── _scan_secrets ───────────────────────────────────────────────────────


class TestScanSecrets:
    def test_no_secrets_clean(self, tmp_path: Path):
        (tmp_path / "clean.js").write_text("const x = 1;\n")
        assert _scan_secrets(tmp_path) == []

    def test_aws_key_detected(self, tmp_path: Path):
        (tmp_path / "bad.js").write_text("const key = 'AKIAIOSFODNN7EXAMPLE';\n")
        hits = _scan_secrets(tmp_path)
        assert len(hits) == 1

    def test_github_token_detected(self, tmp_path: Path):
        (tmp_path / "bad.ts").write_text("const t = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef';")
        hits = _scan_secrets(tmp_path)
        assert len(hits) == 1

    def test_slack_token_detected(self, tmp_path: Path):
        (tmp_path / "app.dart").write_text("final token = 'xoxb-1234567890-abcdefghij';")
        hits = _scan_secrets(tmp_path)
        assert len(hits) == 1

    def test_private_key_detected(self, tmp_path: Path):
        (tmp_path / "key.pem").write_text(
            "-----BEGIN RSA PRIVATE KEY-----\nABC\n-----END RSA PRIVATE KEY-----\n"
        )
        hits = _scan_secrets(tmp_path)
        assert len(hits) == 1

    def test_large_file_skipped(self, tmp_path: Path):
        big = tmp_path / "huge.js"
        big.write_bytes(b"x" * 6_000_000)  # >5MB
        assert _scan_secrets(tmp_path) == []


# ── _run_trivy ─────────────────────────────────────────────────────────


class TestRunTrivy:
    def test_trivy_not_installed_no_report(self):
        with patch("hero.commands.harden.shutil.which", return_value=None):
            findings, note = _run_trivy(Path("/tmp"))
        assert findings == []
        assert "trivy not installed" in note

    def test_trivy_not_installed_with_report(self, tmp_path: Path):
        report = tmp_path / "trivy-report.json"
        report.write_text(json.dumps({
            "Results": [{
                "Vulnerabilities": [
                    {"Severity": "CRITICAL", "PkgID": "pkg1", "Title": "CVE-2024-1"},
                    {"Severity": "HIGH", "PkgID": "pkg2", "Title": "CVE-2024-2"},
                ]
            }]
        }))
        with patch("hero.commands.harden.shutil.which", return_value=None):
            findings, note = _run_trivy(tmp_path)
        assert len(findings) == 1
        assert "CVE-2024-1" in findings[0]
        assert note == ""

    def test_trivy_execution_failure(self):
        with patch("hero.commands.harden.shutil.which", return_value="/usr/bin/trivy"):
            with patch("hero.commands.harden._safe_run", return_value=(None, "timeout")):
                findings, note = _run_trivy(Path("/tmp"))
        assert findings == []
        assert "timeout" in note


# ── Root detection ──────────────────────────────────────────────────────


class TestRootDetection:
    def test_flutter_with_package(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        (p / "pubspec.yaml").write_text(
            (p / "pubspec.yaml").read_text() + "\ndependencies:\n  flutter_jailbreak_detection: ^1.0.0\n"
        )
        found, note = _check_root_detection(p, "flutter")
        assert found is True

    def test_flutter_missing(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        found, note = _check_root_detection(p, "flutter")
        assert found is False
        assert "not found" in note

    def test_unknown_project_type(self, tmp_path: Path):
        found, note = _check_root_detection(tmp_path, "unknown")
        assert found is True
        assert "not applicable" in note


# ── Cert pinning ────────────────────────────────────────────────────────


class TestCertPinning:
    def test_flutter_with_pinning_code(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        lib = p / "lib"
        (lib / "network.dart").write_text(
            "import 'dart:io';\nclass Api { HttpClient client; }\n"
        )
        found, note = _check_cert_pinning(p, "flutter")
        assert found is True

    def test_flutter_missing(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        found, note = _check_cert_pinning(p, "flutter")
        assert found is False

    def test_android_with_network_security_config(self, tmp_path: Path):
        p = tmp_path / "android_app"
        p.mkdir()
        xml_dir = p / "app" / "src" / "main" / "res" / "xml"
        xml_dir.mkdir(parents=True)
        (xml_dir / "network_security_config.xml").write_text("<network-security-config/>\n")
        found, note = _check_cert_pinning(p, "android")
        assert found is True

    def test_android_missing(self, tmp_path: Path):
        p = tmp_path / "android_app"
        p.mkdir()
        found, note = _check_cert_pinning(p, "android")
        assert found is False


# ── Debug symbols ──────────────────────────────────────────────────────


class TestDebugSymbols:
    def test_present(self, tmp_path: Path):
        d = tmp_path / "build" / "debug-info"
        d.mkdir(parents=True)
        (d / "app.android.symbols").write_text("symbols\n")
        ok, note = _check_debug_symbols_stripped(tmp_path)
        assert ok is True
        assert "symbol map" in note

    def test_missing(self, tmp_path: Path):
        ok, note = _check_debug_symbols_stripped(tmp_path)
        assert ok is False
        assert "not found" in note

    def test_empty_directory(self, tmp_path: Path):
        d = tmp_path / "build" / "debug-info"
        d.mkdir(parents=True)
        ok, note = _check_debug_symbols_stripped(tmp_path)
        assert ok is False
        assert "empty" in note


# ── run_harden integration ─────────────────────────────────────────────


class TestRunHarden:
    def test_minimal_flutter_project(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_harden(p, verbose=False)
        assert "sandbox" in result
        assert "score" in result
        assert "checks" in result
        assert "findings" in result
        assert result["project_type"] == "flutter"
        assert 0 <= result["score"] <= 100

    def test_checks_keys_present(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_harden(p)
        expected_checks = {"trivy", "secrets", "root_detection", "cert_pinning", "debug_symbols"}
        assert expected_checks.issubset(result["checks"].keys())

    def test_node_project(self, tmp_path: Path):
        p = _make_node_project(tmp_path)
        result = run_harden(p)
        assert result["project_type"] == "node"

    def test_json_output_structure(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        result = run_harden(p)
        # All top-level keys should be JSON-serialisable
        dumped = json.dumps(result)
        reloaded = json.loads(dumped)
        assert reloaded["score"] == result["score"]


# ── CLI integration ────────────────────────────────────────────────────


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["harden", "--help"])
        assert result.exit_code == 0
        assert "HARDEN" in result.output.upper() or "harden" in result.output.lower()

    def test_dry_run(self, tmp_path: Path):
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["harden", "--sandbox", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    def test_verbose(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["harden", "--sandbox", str(p), "--verbose"])
        assert result.exit_code == 0

    def test_json_output(self, tmp_path: Path):
        p = _make_flutter_project(tmp_path)
        runner = CliRunner()
        from hero.cli import main
        result = runner.invoke(main, ["harden", "--sandbox", str(p), "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "score" in parsed
