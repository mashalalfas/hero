"""Tests for hero legal command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hero.commands.legal import (
    _check_copyright,
    _check_eula,
    _check_license_scan,
    _check_privacy_policy,
    _check_sbom,
    _compute_legal_score,
    _detect_project_type,
    _load_or_create_legal_config,
    _resolve_sandbox,
    _scan_licenses_flutter,
    _scan_licenses_node,
    _write_text,
    DEFAULT_LEGAL_CONFIG,
    EULA_TEMPLATE_PATH,
    OPENTERMS_SRC,
    run_legal,
    legal,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal flutter-like project for testing."""
    (tmp_path / "pubspec.yaml").write_text("name: test_app\nversion: 1.0.0\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "main.dart").write_text(
        '// SPDX-License-Identifier: MIT\n// Copyright 2024 Test\nvoid main() {}\n'
    )
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "widget_test.dart").write_text(
        '// SPDX-License-Identifier: MIT\nimport "package:flutter_test/flutter_test.dart";\n'
    )
    return tmp_path


@pytest.fixture
def tmp_node_project(tmp_path: Path) -> Path:
    """Create a minimal node.js project for testing."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "test-node", "version": "1.0.0", "dependencies": {}})
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text(
        '// SPDX-License-Identifier: MIT\n// Copyright 2024 Test\nconsole.log("hi");\n'
    )
    return tmp_path


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_flutter_lock(tmp_path: Path) -> None:
    """Write a minimal pubspec.lock with known licences."""
    # Fix: _check_license_scan calls _detect_project_type which needs pubspec.yaml
    (tmp_path / "pubspec.yaml").write_text("name: test\nversion: 1.0.0\n")
    content = """\
packages:
  flutter:
    dependency: "direct main"
    description:
      path: "flutter"
      url: "https://flutter.dev"
    source: hosted
    version: "0.0.0"
    sdks:
      dart: ">=3.0.0 <4.0.0"
  cupertino_icons:
    dependency: "direct main"
    description:
      name: cupertino_icons
      url: "https://pub.dev"
    source: hosted
    version: "1.0.8"
    license: "BSD-3-Clause"
  provider:
    dependency: "direct main"
    description:
      name: provider
      url: "https://pub.dev"
    source: hosted
    version: "6.1.2"
    license: "MIT"
  gpl_blocked_pkg:
    dependency: "direct main"
    description:
      name: gpl_blocked_pkg
      url: "https://pub.dev"
    source: hosted
    version: "1.0.0"
    license: "GPL-3.0"
"""
    (tmp_path / "pubspec.lock").write_text(content)


# ── Resolve sandbox ─────────────────────────────────────────────────────


class TestResolveSandbox:
    def test_direct_path(self, tmp_path: Path):
        result = _resolve_sandbox(str(tmp_path))
        assert result == tmp_path

    def test_development_fallback(self, tmp_path: Path):
        dev = tmp_path / "Development" / "MyApp"
        dev.mkdir(parents=True)
        with patch("hero.commands.pre_commit.Path.home", return_value=tmp_path):
            result = _resolve_sandbox("MyApp")
        assert result == dev


# ── Config ───────────────────────────────────────────────────────────────


class TestLoadOrCreateLegalConfig:
    def test_existing_config(self, tmp_path: Path):
        config_data = {"project": "existing", "jurisdiction": "US"}
        (tmp_path / "legal-config.json").write_text(json.dumps(config_data))
        config, auto = _load_or_create_legal_config(tmp_path)
        assert config["project"] == "existing"
        assert auto is False

    def test_missing_config_creates_default(self, tmp_path: Path):
        config, auto = _load_or_create_legal_config(tmp_path)
        assert auto is True
        assert config["jurisdiction"] == "UAE"
        assert "MIT" in config["ossAllowlist"]
        assert "GPL-3.0" in config["ossBlocklist"]
        assert (tmp_path / "legal-config.json").exists()

    def test_auto_detects_project_name_from_pubspec(self, tmp_path: Path):
        (tmp_path / "pubspec.yaml").write_text("name: melody_app\nversion: 1.0.0\n")
        config, auto = _load_or_create_legal_config(tmp_path)
        assert config["project"] == "melody_app"
        assert auto is True

    def test_auto_detects_project_name_from_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "my-node-app"}))
        config, auto = _load_or_create_legal_config(tmp_path)
        assert config["project"] == "my-node-app"
        assert auto is True

    def test_corrupt_config_regenerates(self, tmp_path: Path):
        (tmp_path / "legal-config.json").write_text("not json{{")
        config, auto = _load_or_create_legal_config(tmp_path)
        assert auto is True
        assert (tmp_path / "legal-config.json").exists()


# ── License scan ─────────────────────────────────────────────────────────


class TestScanLicensesFlutter:
    def test_parse_pubspec_lock(self, tmp_path: Path):
        _make_flutter_lock(tmp_path)
        entries, err = _scan_licenses_flutter(tmp_path)
        assert err is None
        names = {e["name"] for e in entries}
        assert "provider" in names
        assert "cupertino_icons" in names
        assert "gpl_blocked_pkg" in names
        for e in entries:
            if e["name"] == "provider":
                assert e["license"] == "MIT"

    def test_missing_lock_file(self, tmp_path: Path):
        entries, err = _scan_licenses_flutter(tmp_path)
        assert entries == []
        assert err is not None


class TestScanLicensesNode:
    def test_parse_package_lock(self, tmp_path: Path):
        lock_data = {
            "name": "test-node",
            "version": "1.0.0",
            "packages": {
                "": {"name": "test-node", "version": "1.0.0"},
                "node_modules/lodash": {
                    "version": "4.17.21",
                    "license": "MIT",
                },
                "node_modules/blocked-pkg": {
                    "version": "1.0.0",
                    "license": "GPL-2.0",
                },
            },
        }
        (tmp_path / "package-lock.json").write_text(json.dumps(lock_data))
        # Fix: _detect_project_type needs package.json to identify a Node project
        (tmp_path / "package.json").write_text('{"name":"test","version":"1.0.0"}')
        entries, err = _scan_licenses_node(tmp_path)
        assert err is None
        names = {e["name"] for e in entries}
        assert "lodash" in names
        assert "blocked-pkg" in names

    def test_license_checker_json_output(self, tmp_path: Path):
        lc_output = {
            "lodash@4.17.21": {"licenses": "MIT", "repository": "https://github.com/lodash/lodash"},
            "express@4.18.0": {"licenses": "Apache-2.0"},
        }
        (tmp_path / "package-lock.json").write_text(json.dumps({"version": ""}))

        fake_result = type("R", (), {"stdout": json.dumps(lc_output), "returncode": 0})()
        with patch("hero.commands.legal._safe_run", return_value=(fake_result, None)):
            entries, err = _scan_licenses_node(tmp_path)
        assert err is None
        names = {e["name"] for e in entries}
        assert "lodash" in names


class TestCheckLicenseScan:
    def test_all_allowlisted(self, tmp_path: Path):
        _make_flutter_lock(tmp_path)
        config = {
            "ossAllowlist": ["MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0", "ISC"],
            "ossBlocklist": ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"],
        }
        result = _check_license_scan(tmp_path, config, verbose=False)
        # Should still have GPL package in results, but flag it
        assert result["blocked_count"] == 1
        assert result["passed"] is False

    def test_no_blocked_licenses(self, tmp_path: Path):
        # Only MIT licences
        content = """\
packages:
  provider:
    dependency: "direct main"
    description:
      name: provider
      url: "https://pub.dev"
    source: hosted
    version: "6.1.2"
    license: "MIT"
"""
        (tmp_path / "pubspec.lock").write_text(content)
        config = {
            "ossAllowlist": ["MIT"],
            "ossBlocklist": ["GPL-3.0"],
        }
        result = _check_license_scan(tmp_path, config, verbose=False)
        assert result["passed"] is True
        assert result["blocked_count"] == 0

    def test_blocked_license_deducted(self, tmp_path: Path):
        _make_flutter_lock(tmp_path)
        config = {
            "ossAllowlist": ["MIT"],
            "ossBlocklist": ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"],
        }
        result = _check_license_scan(tmp_path, config, verbose=False)
        assert result["blocked_count"] >= 1


# ── SBOM ─────────────────────────────────────────────────────────────────


class TestCheckSbom:
    def test_sbom_generated_flutter(self, tmp_path: Path):
        _make_flutter_lock(tmp_path)
        (tmp_path / "pubspec.yaml").write_text("name: test_app\nversion: 1.0.0\n")
        result = _check_sbom(tmp_path, verbose=False)
        assert result["passed"] is True
        assert "sbom.json" in result["summary"]
        sbom_path = tmp_path / "legal" / "sbom.json"
        assert sbom_path.exists()
        data = json.loads(sbom_path.read_text())
        assert "components" in data

    def test_sbom_generated_node(self, tmp_path: Path):
        lock_data = {
            "name": "test",
            "version": "1.0.0",
            "packages": {
                "": {"name": "test", "version": "1.0.0"},
                "node_modules/lodash": {"version": "4.17.21", "license": "MIT"},
            },
        }
        (tmp_path / "package-lock.json").write_text(json.dumps(lock_data))
        (tmp_path / "package.json").write_text(json.dumps({"name": "test"}))
        # patch out the npx call so it falls back to manual generation
        with patch("hero.commands.legal._safe_run", return_value=(None, "npx not found")):
            result = _check_sbom(tmp_path, verbose=False)
        assert result["passed"] is True
        assert (tmp_path / "legal" / "sbom.json").exists()

    def test_sbom_missing_lock_file(self, tmp_path: Path):
        (tmp_path / "pubspec.yaml").write_text("name: test_app\n")
        result = _check_sbom(tmp_path, verbose=False)
        assert result["passed"] is False

    def test_sbom_unknown_project_type(self, tmp_path: Path):
        result = _check_sbom(tmp_path, verbose=False)
        assert result["passed"] is False


# ── EULA ─────────────────────────────────────────────────────────────────


class TestCheckEula:
    def test_eula_generated(self, tmp_path: Path, tmp_project: Path):
        # Point template to a fixture
        fake_template = tmp_path / "License.md"
        fake_template.write_text("EULA for [NAME HERE], machine [NUM], year [YEAR], jurisdiction [JURISDICTION]")
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", fake_template):
            config = {"project": "MyApp", "jurisdiction": "UAE"}
            result = _check_eula(tmp_project, config, verbose=False)
        assert result["passed"] is True
        eula_path = tmp_project / "legal" / "EULA.md"
        assert eula_path.exists()
        content = eula_path.read_text()
        assert "MyApp" in content
        assert "1" in content

    def test_eula_template_missing(self, tmp_path: Path, tmp_project: Path):
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_path / "nonexistent.md"):
            config = {"project": "MyApp", "jurisdiction": "UAE"}
            result = _check_eula(tmp_project, config, verbose=False)
        assert result["passed"] is False

    def test_eula_creates_legal_dir(self, tmp_path: Path):
        fake_template = tmp_path / "License.md"
        fake_template.write_text("EULA for [NAME HERE]")
        config = {"project": "TestApp", "jurisdiction": "UAE"}
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", fake_template):
            _check_eula(tmp_path, config, verbose=False)
        assert (tmp_path / "legal" / "EULA.md").exists()


# ── Privacy Policy ──────────────────────────────────────────────────────


class TestCheckPrivacyPolicy:
    def test_openterms_unavailable_uses_fallback(self, tmp_path: Path):
        with patch("hero.commands.legal._generate_privacy_via_openterms", return_value=None):
            config = {"project": "MyApp"}
            result = _check_privacy_policy(tmp_path, config, verbose=False)
        assert result["passed"] is True
        assert result["used_fallback"] is True
        assert "fallback" in result["summary"]
        privacy_path = tmp_path / "legal" / "PRIVACY.md"
        assert privacy_path.exists()
        content = privacy_path.read_text()
        assert "Privacy Policy" in content

    def test_openterms_succeeds(self, tmp_path: Path):
        with patch(
            "hero.commands.legal._generate_privacy_via_openterms",
            return_value="# Generated Privacy Policy\nby openterms",
        ):
            config = {"project": "MyApp"}
            result = _check_privacy_policy(tmp_path, config, verbose=False)
        assert result["passed"] is True
        assert result["used_fallback"] is False
        assert "openterms" in result["summary"]

    def test_fallback_template_content(self, tmp_path: Path):
        with patch("hero.commands.legal._generate_privacy_via_openterms", return_value=None):
            config = {"project": "TestApp"}
            result = _check_privacy_policy(tmp_path, config, verbose=False)
        content = (tmp_path / "legal" / "PRIVACY.md").read_text()
        assert "does not collect" in content.lower()
        assert "TestApp" in content


# ── Copyright (re-use) ──────────────────────────────────────────────────


class TestCopyrightReuse:
    def test_reuses_pre_commit_copyright(self, tmp_project: Path):
        result = _check_copyright(tmp_project, verbose=False)
        assert "passed" in result
        assert "summary" in result
        assert "missing" in result

    def test_missing_headers_detected(self, tmp_path: Path):
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "no_header.dart").write_text("void main() {}\n")
        result = _check_copyright(tmp_path, verbose=False)
        assert result["missing"] == 1
        assert result["passed"] is False


# ── Scoring ─────────────────────────────────────────────────────────────


class TestComputeLegalScore:
    def test_clean_project_full_score(self):
        config = {"passed": True, "summary": "ok", "auto_generated": False}
        license_r = {"passed": True, "summary": "clean", "blocked_count": 0, "blocked": []}
        sbom = {"passed": True, "summary": "ok"}
        eula = {"passed": True, "summary": "ok"}
        privacy = {"passed": True, "summary": "ok", "used_fallback": False}
        copyright_r = {"passed": True, "summary": "ok", "missing": 0}
        score, findings = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 100
        assert findings == []

    def test_auto_generated_config_deducts_15(self):
        config = {"passed": True, "auto_generated": True}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True, "summary": "ok"}
        eula = {"passed": True, "summary": "ok"}
        privacy = {"passed": True, "summary": "ok", "used_fallback": False}
        copyright_r = {"passed": True, "missing": 0}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 85

    def test_blocked_licenses_deduct_15_each(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {
            "passed": False,
            "blocked_count": 2,
            "blocked": [
                {"name": "pkg-a", "license": "GPL-3.0"},
                {"name": "pkg-b", "license": "AGPL-3.0"},
            ],
        }
        sbom = {"passed": True}
        eula = {"passed": True}
        privacy = {"passed": True, "used_fallback": False}
        copyright_r = {"passed": True, "missing": 0}
        score, findings = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 70  # 100 - 30
        assert len(findings) == 2

    def test_sbom_missing_deducts_20(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": False, "summary": "missing"}
        eula = {"passed": True}
        privacy = {"passed": True, "used_fallback": False}
        copyright_r = {"passed": True, "missing": 0}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 80

    def test_eula_missing_deducts_20(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True}
        eula = {"passed": False, "summary": "not generated"}
        privacy = {"passed": True, "used_fallback": False}
        copyright_r = {"passed": True, "missing": 0}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 80

    def test_privacy_fallback_deducts_5(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True}
        eula = {"passed": True}
        privacy = {"passed": True, "used_fallback": True}
        copyright_r = {"passed": True, "missing": 0}
        score, findings = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 95
        assert any("fallback" in f["message"] for f in findings)

    def test_privacy_missing_deducts_15(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True}
        eula = {"passed": True}
        privacy = {"passed": False}
        copyright_r = {"passed": True, "missing": 0}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 85

    def test_copyright_headers_deduct_2_per_missing(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True}
        eula = {"passed": True}
        privacy = {"passed": True, "used_fallback": False}
        copyright_r = {"passed": False, "missing": 3}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 94  # 100 - 6

    def test_floor_at_zero(self):
        config = {"passed": True, "auto_generated": False}
        license_r = {
            "passed": False,
            "blocked_count": 10,
            "blocked": [{"name": f"pkg-{i}", "license": "GPL-3.0"} for i in range(10)],
        }
        sbom = {"passed": False}
        eula = {"passed": False}
        privacy = {"passed": False}
        copyright_r = {"passed": False, "missing": 10}
        score, _ = _compute_legal_score(config, license_r, sbom, eula, privacy, copyright_r)
        assert score == 0

    def test_status_thresholds(self):
        """Score >= 70 = pass, 50-69 = warn, <50 = fail."""
        config = {"passed": True, "auto_generated": False}
        license_r = {"passed": True, "blocked_count": 0, "blocked": []}
        sbom = {"passed": True}
        eula = {"passed": True}
        privacy = {"passed": True, "used_fallback": False}

        def _score_for(copyright_missing: int) -> tuple[int, str, bool]:
            cr = {"passed": copyright_missing == 0, "missing": copyright_missing}
            score, _ = _compute_legal_score(
                config, license_r, sbom, eula, privacy, cr
            )
            if score >= 70:
                return score, "pass", True
            elif score >= 50:
                return score, "warn", True
            else:
                return score, "fail", False

        # 0 missing headers: 100 → pass
        s, st, p = _score_for(0)
        assert st == "pass"
        assert p is True

        # 25 missing headers: 100 - 50 = 50 → warn
        s, st, p = _score_for(25)
        assert st == "warn"
        assert p is True

        # 26 missing headers: 100 - 52 = 48 → fail
        s, st, p = _score_for(26)
        assert st == "fail"
        assert p is False


# ── run_legal integration ────────────────────────────────────────────────


class TestRunLegal:
    def test_clean_project(self, tmp_project: Path):
        # Add a legal-config.json
        (tmp_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test_app",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT", "BSD-3-Clause"],
                "ossBlocklist": ["GPL-3.0", "AGPL-3.0", "SSPL"],
            })
        )
        _make_flutter_lock(tmp_project)

        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = run_legal(tmp_project, verbose=False)

        assert "sandbox" in result
        assert "score" in result
        assert "checks" in result
        assert "findings" in result
        assert 0 <= result["score"] <= 100
        assert result["status"] in ("pass", "warn", "fail")
        assert result["checks"]["config"]["passed"] is True
        assert result["checks"]["copyright"]["passed"] is True

    def test_dry_run_does_not_write(self, tmp_project: Path):
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a minimal project
            Path("pubspec.yaml").write_text("name: test\n")
            Path("lib").mkdir()
            Path("lib/main.dart").write_text("// SPDX-License-Identifier: MIT\nvoid main() {}\n")
            # We can't easily test dry-run with a temp dir since _resolve_sandbox needs it
            # to be in ~/Development or similar. Skip — covered by functional test.
            pytest.skip("dry-run tested functionally")

    def test_auto_generated_config_deducts(self, tmp_project: Path):
        """Missing legal-config.json → auto-generated → score deducted."""
        _make_flutter_lock(tmp_project)

        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = run_legal(tmp_project, verbose=False)

        assert result["checks"]["config"]["auto_generated"] is True
        # Score should be <= 85 (at least -15 for auto-generated config)
        assert result["score"] <= 85

    def test_blocked_licenses_deduct(self, tmp_project: Path):
        _make_flutter_lock(tmp_project)
        (tmp_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test_app",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT"],
                "ossBlocklist": ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"],
            })
        )
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = run_legal(tmp_project, verbose=False)
        assert result["checks"]["license_scan"]["blocked_count"] >= 1
        assert result["checks"]["license_scan"]["passed"] is False


# ── CLI command ──────────────────────────────────────────────────────────


class TestLegalCLI:
    def test_help(self, runner):
        result = runner.invoke(legal, ["--help"])
        assert result.exit_code == 0
        assert "LEGAL" in result.output or "legal" in result.output.lower()

    def test_missing_sandbox_exits(self, runner):
        result = runner.invoke(legal, ["--sandbox", "nonexistent_sandbox_xyzzy"])
        assert result.exit_code != 0

    def test_json_output(self, runner, tmp_project: Path):
        (tmp_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test_app",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT"],
                "ossBlocklist": ["GPL-3.0"],
            })
        )
        _make_flutter_lock(tmp_project)
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = runner.invoke(legal, ["--sandbox", str(tmp_project), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sandbox" in data
        assert "score" in data
        assert "checks" in data

    def test_dry_run(self, runner, tmp_project: Path):
        # Ensure no legal dir exists before dry-run
        legal_dir = tmp_project / "legal"
        if legal_dir.exists():
            import shutil
            shutil.rmtree(legal_dir)

        with patch("hero.commands.legal._resolve_sandbox", return_value=tmp_project):
            result = runner.invoke(legal, ["--sandbox", str(tmp_project), "--dry-run"])

        assert result.exit_code == 0
        assert "dry run" in result.output.lower() or "No files written" in result.output
        # Verify nothing was written
        assert not (tmp_project / "legal").exists()

    def test_files_generated(self, tmp_project: Path):
        """Verify legal artifacts are written after a real run."""
        (tmp_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test_app",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT"],
                "ossBlocklist": ["GPL-3.0"],
            })
        )
        _make_flutter_lock(tmp_project)

        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = run_legal(tmp_project, verbose=False)

        legal_dir = tmp_project / "legal"
        assert legal_dir.exists()
        assert (legal_dir / "EULA.md").exists()
        assert (legal_dir / "PRIVACY.md").exists()
        assert (legal_dir / "sbom.json").exists()


# ── Edge cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_project(self, tmp_path: Path):
        result = run_legal(tmp_path, verbose=False)
        assert 0 <= result["score"] <= 100
        assert result["checks"]["config"]["auto_generated"] is True

    def test_verbose_output(self, tmp_project: Path):
        _make_flutter_lock(tmp_project)
        (tmp_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test_app",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT"],
                "ossBlocklist": ["GPL-3.0"],
            })
        )
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_project / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            result = run_legal(tmp_project, verbose=True)
        # detail fields should be populated (may be empty strings for clean checks)
        assert "detail" in result["checks"]["license_scan"]

    def test_no_copyright_files(self, tmp_path: Path):
        (tmp_path / "pubspec.yaml").write_text("name: empty\n")
        with patch("hero.commands.legal.EULA_TEMPLATE_PATH", tmp_path / "fake_eula.md") as eula_p:
            eula_p.write_text("EULA for [NAME HERE]")
            (tmp_path / "legal-config.json").write_text(
                json.dumps({
                    "project": "empty",
                    "jurisdiction": "UAE",
                    "ossAllowlist": [],
                    "ossBlocklist": [],
                })
            )
            result = run_legal(tmp_path, verbose=False)
        assert result["checks"]["copyright"]["total"] == 0

    def test_node_project_with_blocked_license(self, tmp_node_project: Path):
        # Fix: ensure package.json exists (fixture may not cover all paths)
        (tmp_node_project / "package.json").write_text('{"name":"test-node"}')
        lock_data = {
            "name": "test",
            "version": "1.0.0",
            "packages": {
                "": {"name": "test", "version": "1.0.0"},
                "node_modules/gpl-pkg": {
                    "version": "1.0.0",
                    "license": "GPL-3.0",
                },
            },
        }
        (tmp_node_project / "package-lock.json").write_text(json.dumps(lock_data))
        (tmp_node_project / "legal-config.json").write_text(
            json.dumps({
                "project": "test-node",
                "jurisdiction": "UAE",
                "ossAllowlist": ["MIT"],
                "ossBlocklist": ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"],
            })
        )
        result = run_legal(tmp_node_project, verbose=False)
        assert result["checks"]["license_scan"]["blocked_count"] >= 1
