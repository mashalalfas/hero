"""Phase 6: Performance — N+1 queries, pagination, caching.

Tuned patterns — only flags:
- Actual DB/ORM queries inside loops (not all loops)
- Missing pagination on data-fetching functions
- Hot paths without caching strategy
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase

CODE_EXTENSIONS = {".dart", ".go", ".js", ".ts", ".py", ".rs", ".java"}

# DB query patterns — only these count as N+1
DB_QUERY_PATTERNS = [
    r'\.find\s*\(', r'\.findOne\s*\(', r'\.findAll\s*\(',
    r'\.query\s*\(', r'\.execute\s*\(',
    r'\.select\s*\(', r'\.fetch\s*\(',
    r'\.get\s*\(',  # only in ORM context
    r'SELECT\s+', r'INSERT\s+', r'UPDATE\s+', r'DELETE\s+',
    r'\.where\s*\(', r'\.filter\s*\(',  # ORM chain
]

# Data-fetching function patterns (need pagination)
DATA_FETCH_PATTERNS = [
    r'def\s+list_', r'async\s+def\s+list_',
    r'function\s+get[A-Z]All', r'function\s+list[A-Z]',
    r'\.findAll\s*\(', r'\.findMany\s*\(',
    r'select\s+\*\s+from',
]

# Caching indicators
CACHE_INDICATORS = [
    r'cache', r'Cache', r'redis', r'memcached',
    r'lru_cache', r'@cache', r'memoize', r'stale-while',
]


@register_phase
class PerformancePhase(BasePhase):
    name = "performance"
    number = 6
    description = "Performance audit: N+1 queries, pagination, caching"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)
        project_type = self._detect_project_type(project_path)

        findings: list[dict[str, Any]] = []
        n_plus_one: list[dict[str, Any]] = []
        pagination_gaps: list[str] = []
        caching_issues: list[str] = []

        skip = {"node_modules", ".git", "build", "dist", "target", ".venv", "__pycache__",
                ".dart_tool", "vendor", "ephemeral", ".plugin_symlinks"}

        for f in project_path.rglob("*"):
            if not f.is_file():
                continue
            if any(s in f.parts for s in skip):
                continue
            if f.suffix not in CODE_EXTENSIONS:
                continue
            # Skip test files
            if self._is_test_file(f):
                continue

            try:
                content = f.read_text(errors="ignore")
                lines = content.split("\n")
                rel = str(f.relative_to(project_path))
            except (OSError, PermissionError):
                continue

            # N+1 query detection: DB queries inside loops
            in_loop = False
            loop_start = 0
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if re.match(r'for\s+', stripped) or re.match(r'while\s+', stripped):
                    in_loop = True
                    loop_start = i
                elif in_loop and i > loop_start + 20:
                    in_loop = False

                if in_loop and self._is_db_query(stripped):
                    n_plus_one.append({"file": rel, "line": i})
                    findings.append({"severity": "major", "title": f"N+1 query in {rel}:{i}",
                                     "detail": stripped[:100]})

            # Pagination check: only for data-fetching functions
            for i, line in enumerate(lines, 1):
                if self._is_data_fetch(line):
                    block = "\n".join(lines[max(0, i-2):min(len(lines), i+8)])
                    if not re.search(r'(LIMIT|OFFSET|take|skip|paginate|cursor|page|per_page|pageSize)', block, re.IGNORECASE):
                        pagination_gaps.append(f"{rel}:{i}")
                        findings.append({"severity": "minor", "title": f"Missing pagination in {rel}:{i}"})

            # Caching check: only for heavy data functions
            for i, line in enumerate(lines, 1):
                if re.search(r'(def\s+get_|async\s+def\s+fetch|function\s+load[A-Z])', line, re.IGNORECASE):
                    block = "\n".join(lines[max(0, i-1):min(len(lines), i+15)])
                    if not any(re.search(ind, block, re.IGNORECASE) for ind in CACHE_INDICATORS):
                        caching_issues.append(f"{rel}:{i}")

        # Deduplicate
        seen = set()
        unique_findings = []
        for f in findings:
            key = f["title"]
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        # Score
        score = 100
        score -= len(n_plus_one) * 8
        score -= min(len(pagination_gaps) * 4, 20)
        score -= min(len(caching_issues) * 2, 10)
        score = max(0, min(100, score))

        report = {
            "projectType": project_type,
            "nPlusOneQueries": len(n_plus_one),
            "paginationGaps": len(pagination_gaps),
            "cachingIssues": len(caching_issues),
            "findings": unique_findings,
        }
        (report_dir / "performance.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=unique_findings,
            summary=f"N+1: {len(n_plus_one)}, Pagination: {len(pagination_gaps)}, Caching: {len(caching_issues)}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _is_test_file(self, path: Path) -> bool:
        """Check if a file is a test file."""
        name = path.name.lower()
        parts = [p.lower() for p in path.parts]
        test_indicators = {"test", "tests", "__tests__", "spec", "specs", ".test.", ".spec.", "_test.", "test_"}
        return any(d in parts for d in test_indicators) or any(ind in name for ind in test_indicators)

    def _is_db_query(self, line: str) -> bool:
        """Check if a line contains an actual DB/ORM query."""
        return any(re.search(p, line, re.IGNORECASE) for p in DB_QUERY_PATTERNS)

    def _is_data_fetch(self, line: str) -> bool:
        """Check if a line is a data-fetching function."""
        return any(re.search(p, line, re.IGNORECASE) for p in DATA_FETCH_PATTERNS)
