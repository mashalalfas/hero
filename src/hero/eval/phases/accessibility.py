"""Phase 7: Accessibility — Basic a11y checks for web projects."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from hero.eval.phases import BasePhase, PhaseResult, register_phase

HTML_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}


@register_phase
class AccessibilityPhase(BasePhase):
    name = "accessibility"
    number = 7
    description = "Accessibility audit for web/UI projects"

    def run(self, project_path: Path, eval_dir: Path, context: dict[str, Any]) -> PhaseResult:
        start = time.time()
        report_dir = eval_dir / "phases"
        report_dir.mkdir(parents=True, exist_ok=True)
        project_type = self._detect_project_type(project_path)

        findings: list[dict[str, Any]] = []
        html_files = 0

        skip = {"node_modules", ".git", "build", "dist", "target", ".venv", "__pycache__",
                ".dart_tool", "vendor", "ephemeral", ".plugin_symlinks"}

        for f in project_path.rglob("*"):
            if not f.is_file():
                continue
            if any(s in f.parts for s in skip):
                continue

            if f.suffix in HTML_EXTENSIONS:
                html_files += 1
                try:
                    content = f.read_text(errors="ignore")
                    rel = str(f.relative_to(project_path))
                except (OSError, PermissionError):
                    continue

                # Missing alt text on images
                imgs = re.findall(r'<img\s[^>]*>', content, re.IGNORECASE)
                for img in imgs:
                    if 'alt=' not in img.lower():
                        findings.append({"severity": "minor", "title": f"Missing alt text in {rel}", "detail": img[:80]})

                # Missing form labels
                inputs = re.findall(r'<input\s[^>]*>', content, re.IGNORECASE)
                for inp in inputs:
                    if 'type="hidden"' in inp.lower() or 'type="submit"' in inp.lower():
                        continue
                    if 'aria-label' not in inp.lower() and 'id=' not in inp.lower():
                        findings.append({"severity": "minor", "title": f"Missing label for input in {rel}"})

                # Missing lang attribute
                if '<html' in content.lower() and 'lang=' not in content.lower():
                    findings.append({"severity": "minor", "title": f"Missing lang attribute in {rel}"})

                # Missing heading hierarchy
                headings = re.findall(r'<h(\d)', content, re.IGNORECASE)
                if headings:
                    levels = [int(h) for h in headings]
                    for i in range(1, len(levels)):
                        if levels[i] - levels[i-1] > 1:
                            findings.append({"severity": "nit", "title": f"Heading skip in {rel}: h{levels[i-1]} to h{levels[i]}"})
                            break

        # If not a web project, skip with neutral score
        if html_files == 0 and project_type in ("go", "python", "rust"):
            return PhaseResult(
                phase_name=self.name, phase_number=self.number,
                status="skipped", score=80,
                summary="Not a web project — a11y skipped",
                duration_seconds=time.time() - start,
            )

        # Score
        score = 100
        score -= len(findings) * 3
        score = max(0, min(100, score))

        report = {
            "htmlFiles": html_files,
            "findings": findings,
        }
        (report_dir / "accessibility.json").write_text(json.dumps(report, indent=2))

        return PhaseResult(
            phase_name=self.name, phase_number=self.number,
            status="completed", score=score, findings=findings,
            summary=f"HTML files: {html_files}, Issues: {len(findings)}",
            duration_seconds=time.time() - start,
            details=report,
        )
