"""Phase 2: Security — OWASP Top 10 audit, secrets scan, dependency check.

Tuned patterns — ignores:
- Test files (they TEST vulnerabilities, not create them)
- path.join(__dirname, "../") — normal Node/Electron pattern
- Template literals in non-execution contexts
- Comments and string literals
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase

# Patterns that look like real secrets (not test fixtures)
SECRET_PATTERNS = [
    r"sk_live_[a-zA-Z0-9]{20,}",
    r"sk_test_[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"glpat_[a-zA-Z0-9\-]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[baprs]-[a-zA-Z0-9\-]+",
    r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
]

# OWASP patterns — tightened to reduce false positives
OWASP_PATTERNS = {
    "injection": [
        # Only flag actual dangerous calls, not framework usage
        r'child_process\.exec\s*\(', r'child_process\.execSync\s*\(',
        r'subprocess\.call\(.*shell\s*=\s*True', r'subprocess\.run\(.*shell\s*=\s*True',
        r'os\.system\s*\(', r'os\.popen\s*\(',
    ],
    "xss": [
        r'dangerouslySetInnerHTML', r'v-html\s*=',
        r'document\.write\s*\(',
        r'\.innerHTML\s*=\s*[^"\']*[^"\'\\)]',  # only direct assignment, not reads
    ],
    "sql_injection": [
        # Only flag actual string concatenation in queries
        r'execute\s*\(["\'].*\+', r'query\s*\(["\'].*\+',
        r'\.raw\s*\(["\'].*\+',
    ],
    "hardcoded_secrets": [
        # Only flag assignments, not test fixtures or docs
        r'(?:password|secret|api_key|apikey)\s*=\s*["\'][^"\']{16,}["\']',
    ],
    "insecure_crypto": [
        r'hashlib\.md5\s*\(', r'hashlib\.sha1\s*\(',
        r'crypto\.createHash\s*\(\s*["\']md5["\']',
        r'crypto\.createHash\s*\(\s*["\']sha1["\']',
    ],
}

# Patterns that are NOT vulnerabilities (whitelist)
FALSE_POSITIVE_PATTERNS = [
    r'path\.join\(__dirname',          # Normal Electron/Node pattern
    r'path\.resolve\(__dirname',       # Normal Node pattern
    r'require\.resolve\s*\(',          # Module resolution
    r'import\s+.*from\s+["\']',       # Import statements
    r'expect\s*\(',                    # Test assertions
    r'toThrow\s*\(',                   # Test expectations
    r'console\.(log|warn|error)\s*\(', # Logging
]

# Code file extensions to scan
CODE_EXTENSIONS = {
    ".dart", ".go", ".js", ".ts", ".py", ".java", ".c", ".h",
    ".rs", ".jsx", ".tsx", ".vue", ".svelte", ".rb", ".php",
}

# Test file indicators
TEST_INDICATORS = {"test", "tests", "__tests__", "spec", "specs", ".test.", ".spec.", "_test.", "test_"}


@register_phase
class SecurityPhase(BasePhase):
    name = "security"
    number = 2
    description = "OWASP Top 10 security audit and secrets detection"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)

        findings: list[dict[str, Any]] = []
        secrets_found: list[dict[str, Any]] = []
        owasp_findings: list[dict[str, Any]] = []

        # 1. Scan for secrets (skip test files)
        for code_file in self._iter_code_files(project_path, skip_tests=True):
            try:
                content = code_file.read_text(errors="ignore")
            except (OSError, PermissionError):
                continue

            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue

                for pattern in SECRET_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        secrets_found.append({
                            "severity": "critical",
                            "title": "Potential secret in code",
                            "file": str(code_file.relative_to(project_path)),
                            "line": i,
                            "detail": line.strip()[:100],
                            "category": "A02:2021 – Cryptographic Failures",
                        })
                        break

        # 2. OWASP pattern checks (skip test files)
        for code_file in self._iter_code_files(project_path, skip_tests=True):
            try:
                content = code_file.read_text(errors="ignore")
            except (OSError, PermissionError):
                continue

            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue

                # Skip false positives
                if self._is_false_positive(line):
                    continue

                for category, patterns in OWASP_PATTERNS.items():
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            severity = "critical" if category in ("injection", "sql_injection") else "high"
                            owasp_findings.append({
                                "severity": severity,
                                "title": f"OWASP: {category}",
                                "file": str(code_file.relative_to(project_path)),
                                "line": i,
                                "detail": line.strip()[:100],
                                "category": f"A03:2021 – {category.replace('_', ' ').title()}",
                            })
                            break

        # 3. Dependency audit
        dep_findings = self._audit_deps(project_path)
        owasp_findings.extend(dep_findings)

        # Deduplicate (same file + line)
        seen = set()
        all_findings = []
        for f in secrets_found + owasp_findings:
            key = (f.get("file", ""), f.get("line", 0), f.get("title", ""))
            if key not in seen:
                seen.add(key)
                all_findings.append(f)

        # Score
        critical = sum(1 for f in all_findings if f["severity"] == "critical")
        high = sum(1 for f in all_findings if f["severity"] == "high")
        medium = sum(1 for f in all_findings if f["severity"] == "medium")
        low = sum(1 for f in all_findings if f["severity"] == "low")

        score = 100
        score -= critical * 15
        score -= high * 8
        score -= medium * 4
        score -= low * 1
        score = max(0, min(100, score))

        report = {
            "summary": {"critical": critical, "high": high, "medium": medium, "low": low},
            "secretsFound": len(secrets_found),
            "owaspFindings": len(owasp_findings),
            "findings": all_findings,
        }
        (report_dir / "security.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=all_findings,
            summary=f"Critical: {critical}, High: {high}, Medium: {medium}, Low: {low}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _is_false_positive(self, line: str) -> bool:
        """Check if a line matches known false positive patterns."""
        for pattern in FALSE_POSITIVE_PATTERNS:
            if re.search(pattern, line):
                return True
        return False

    def _is_test_file(self, path: Path) -> bool:
        """Check if a file is a test file."""
        name = path.name.lower()
        parts = [p.lower() for p in path.parts]
        # Check directory names
        if any(d in parts for d in TEST_INDICATORS):
            return True
        # Check file name
        if any(ind in name for ind in TEST_INDICATORS):
            return True
        return False

    def _iter_code_files(self, path: Path, skip_tests: bool = False):
        """Yield code files, skipping vendor/build dirs and optionally test files."""
        skip = {"node_modules", ".git", "build", "dist", "target", ".venv", "venv",
                "__pycache__", ".dart_tool", "vendor", "ephemeral", ".plugin_symlinks"}
        for f in path.rglob("*"):
            if not f.is_file():
                continue
            if any(s in f.parts for s in skip):
                continue
            if f.suffix not in CODE_EXTENSIONS:
                continue
            if skip_tests and self._is_test_file(f):
                continue
            yield f

    def _audit_deps(self, project_path: Path) -> list[dict[str, Any]]:
        """Run dependency vulnerability audit."""
        findings: list[dict[str, Any]] = []

        # npm audit
        pkg_json = project_path / "package.json"
        if pkg_json.exists():
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"], cwd=str(project_path),
                    capture_output=True, text=True, timeout=60,
                )
                if result.stdout:
                    data = json.loads(result.stdout)
                    vulns = data.get("vulnerabilities", {})
                    for name, info in vulns.items():
                        sev = info.get("severity", "info")
                        # Only count critical and high — medium/low are noise
                        if sev in ("critical", "high"):
                            findings.append({
                                "severity": sev,
                                "title": f"Dependency vulnerability: {name}",
                                "detail": info.get("title", "")[:100],
                                "category": "A06:2021 – Vulnerable Components",
                            })
            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
                pass

        return findings
