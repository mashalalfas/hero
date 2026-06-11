"""Phase 3: Code Review — 5-axis scoring (correctness, readability, architecture, security, performance)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase

CODE_EXTENSIONS = {
    ".dart", ".go", ".js", ".ts", ".py", ".java", ".c", ".h",
    ".rs", ".jsx", ".tsx", ".vue", ".svelte", ".rb", ".php",
}


@register_phase
class CodeReviewPhase(BasePhase):
    name = "code-review"
    number = 3
    description = "5-axis code review: correctness, readability, architecture, security, performance"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)

        files = list(self._iter_code_files(project_path))
        findings: list[dict[str, Any]] = []

        axes = {
            "correctness": {"score": 100, "issues": []},
            "readability": {"score": 100, "issues": []},
            "architecture": {"score": 100, "issues": []},
            "security": {"score": 100, "issues": []},
            "performance": {"score": 100, "issues": []},
        }

        for f in files:
            try:
                content = f.read_text(errors="ignore")
                lines = content.split("\n")
                rel = str(f.relative_to(project_path))
            except (OSError, PermissionError):
                continue

            # --- Correctness checks ---
            # TODO/FIXME/HACK
            for i, line in enumerate(lines, 1):
                if re.match(r'\s*(//|#|/\*|""")\s*(TODO|FIXME|HACK|XXX)', line, re.IGNORECASE):
                    axes["correctness"]["issues"].append(f"{rel}:{i}")
                    findings.append({"severity": "minor", "title": f"TODO/FIXME in {rel}:{i}", "axis": "correctness"})

            # --- Readability checks ---
            # Large files (>500 LOC)
            if len(lines) > 500:
                axes["readability"]["issues"].append(rel)
                findings.append({"severity": "major", "title": f"Large file: {rel} ({len(lines)} lines)", "axis": "readability",
                                 "detail": "Consider splitting into smaller modules"})

            # Deep nesting (>4 levels)
            max_depth = 0
            for line in lines:
                if line.strip() and not line.strip().startswith(("#", "//", "/*", "*")):
                    depth = (len(line) - len(line.lstrip())) // 4
                    max_depth = max(max_depth, depth)
            if max_depth > 4:
                axes["readability"]["issues"].append(f"{rel} (depth={max_depth})")
                findings.append({"severity": "minor", "title": f"Deep nesting in {rel} ({max_depth} levels)", "axis": "readability"})

            # --- Architecture checks ---
            # Import depth (simplified: check for circular-looking patterns)
            if f.suffix == ".py":
                import_count = sum(1 for l in lines if l.strip().startswith("import ") or l.strip().startswith("from "))
                if import_count > 30:
                    axes["architecture"]["issues"].append(rel)
                    findings.append({"severity": "minor", "title": f"High import count in {rel} ({import_count})", "axis": "architecture"})

            # --- Security checks (quick scan) ---
            for i, line in enumerate(lines, 1):
                if re.search(r'\beval\s*\(', line) or re.search(r'\bexec\s*\(', line):
                    axes["security"]["issues"].append(f"{rel}:{i}")
                    findings.append({"severity": "critical", "title": f"eval/exec in {rel}:{i}", "axis": "security"})
                    axes["security"]["score"] -= 15

            # --- Performance checks ---
            # Check for N+1 patterns (simplified)
            for i, line in enumerate(lines, 1):
                if re.search(r'for\s+\w+\s+in\s+.*:', line):
                    # Look for DB queries inside loops (next 5 lines)
                    block = "\n".join(lines[i:min(i+5, len(lines))])
                    if re.search(r'\.(find|query|select|get|fetch|read)\s*\(', block):
                        axes["performance"]["issues"].append(f"{rel}:{i}")
                        findings.append({"severity": "major", "title": f"Possible N+1 in {rel}:{i}", "axis": "performance"})

        # Deduplicate findings
        seen = set()
        unique_findings = []
        for f in findings:
            key = f["title"]
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        # Calculate final scores
        for axis_name, axis_data in axes.items():
            deductions = 0
            for issue in axis_data["issues"]:
                deductions += 2  # simplified
            axis_data["score"] = max(0, min(100, 100 - deductions))

        overall = sum(a["score"] for a in axes.values()) // len(axes)

        report = {
            "axes": {k: {"score": v["score"], "issueCount": len(v["issues"])} for k, v in axes.items()},
            "overallScore": overall,
            "totalFiles": len(files),
            "findings": unique_findings,
        }
        (report_dir / "code-review.json").write_text(json.dumps(report, indent=2))

        axes_summary = ", ".join(f"{k}={v['score']}" for k, v in axes.items())
        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=overall, findings=unique_findings,
            summary=f"Files: {len(files)}, {axes_summary}",
            duration_seconds=time.time() - start,
            details=report,
        )

    def _iter_code_files(self, path: Path):
        skip = {"node_modules", ".git", "build", "dist", "target", ".venv", "venv",
                "__pycache__", ".dart_tool", "vendor", "ephemeral", ".plugin_symlinks"}
        test_indicators = {"test", "tests", "__tests__", "spec", "specs", ".test.", ".spec."}
        for f in path.rglob("*"):
            if not f.is_file():
                continue
            if any(s in f.parts for s in skip):
                continue
            if f.suffix not in CODE_EXTENSIONS:
                continue
            # Skip test files
            name_lower = f.name.lower()
            parts_lower = [p.lower() for p in f.parts]
            if any(d in parts_lower for d in test_indicators):
                continue
            if any(ind in name_lower for ind in test_indicators):
                continue
            yield f
