# COUNCIL DIAGNOSIS — Cross-Platform Failure Post-Mortem

**Session:** `pipeline-website-flutter-fail`  
**Council convened:** automatic — soldier failure cascade (2 consecutive failures on same task type)  
**Quorum:** 3/3 (DeepSeek V4 Pro ×2 + MiMo V2.5 Pro)  
**Consensus:** UNANIMOUS — structural platform-blindness is the root cause  
**Date:** 2026-06-18

---

## 1. DIAGNOSIS — Root Causes for Each Soldier Failure

### Soldier A: Kimi K2.6 — 26 tool calls, silent failure, built nothing

| Layer | Root Cause | Evidence |
|-------|-----------|----------|
| **Context** | Received Flutter project context (PLAN.md, pubspec.yaml, dart files) but task was to build a **website**. No platform hint in injected context. | `build_context()` in `context.py` injects only: sandbox name, budget, katana state, task string. Zero platform/target metadata. |
| **Navigation** | Soldier wanders the Flutter codebase reading files, trying to understand structure. 26 tool calls = exploration, not building. | Flutter codebase is large, soldier has no compass telling it to ignore `lib/` and build in `website/` or root `index.html`. |
| **Output** | No build artifact produced. No explicit failure reported. Soldier exhausts context window or times out silently. | No post-build check validates "did the soldier actually produce output files?" — only checks that soldier process terminated. |
| **Model** | Kimi K2.6 is an agent-reasoning model. Given ambiguous context (Flutter project + "build website" task), it explores rather than commits. | Model lane is correct for code work, but context is fatally underspecified. |

**Verdict:** Kimi didn't fail to build — it failed to understand WHAT to build. The context injection is project-blind, not task-aware. 26 explorations is rational behavior for an agent that received conflicting signals.

### Soldier B: DeepSeek V4 Pro — built wrong thing (old Flutter site)

| Layer | Root Cause | Evidence |
|-------|-----------|----------|
| **Context** | Same context injection as Kimi. Received Flutter project, not website task specification. | `build_context()` is deterministic — same input, same defect. |
| **Navigation** | Soldier read the Flutter project's existing website docs/previous build, assumed the task was TO UPDATE them, not build NEW from spec. | The project has prior Flutter documentation websites. Without "new website from this SPEC" framing, soldier defaults to updating existing content. |
| **Output** | Produced output — but wrong output. No validation caught it. | Pipeline's PRE-COMMIT ran `dart analyze` on the Flutter project, not on the website. Wrong validator, wrong target → passed validation gate despite wrong output. |
| **Model** | DeepSeek V4 Pro favors deep reasoning. It correctly reasoned that the existing Flutter project has a docs website, and updated it. Wrong conclusion from correct reasoning. | Given ambiguous context, the model picked the most likely interpretation. The flaw is in the brief, not the model. |

**Verdict:** DeepSeek didn't build the wrong thing through incompetence — it built the wrong thing because the soldier brief never specified "you are building a standalone website, not updating Flutter docs." The system trained soldiers to conflate "project context" with "task target."

### Shared Root Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│  THE FATAL CHAIN                                                │
│                                                                 │
│  1. _detect_project_type() → pubspec.yaml → "flutter"           │
│  2. build_context() injects Flutter project files as context    │
│  3. Soldier reads Flutter context + "build website" task        │
│  4. Conflict: files say Flutter, task says website              │
│  5. Soldier resolves ambiguity by picking one side              │
│  6. Pipeline runs dart analyze (Flutter validator)              │
│  7. Wrong output passes Flutter lint → validation gate is       │
│     structurally incapable of detecting the error               │
└─────────────────────────────────────────────────────────────────┘
```

**The system conflates two orthogonal concepts:**
- **Source project type** (what EXISTS on disk — detected from files)
- **Target platform type** (what should be BUILT — derived from task)

These must be separate fields, passed independently to soldiers, and used to select validation gates independently.

---

## 2. SYSTEM IMPROVEMENTS — Architecture for Platform Adaptability

### Principle: Separate Source from Target

```
CURRENT (BROKEN)                     FUTURE (FIXED)
─────────────────                    ──────────────
project_type = detect(files)         source_type = detect(files)
           ↓                         target_type = detect(task, spec)
           ↓                                      ↓
    ┌──────┴──────┐                    ┌───────────┴───────────┐
    │  Everything  │                    │  source_type          │
    │  uses this   │                    │  → PRE-COMMIT         │
    │  one field   │                    │    (lint source)      │
    └─────────────┘                    │                       │
                                       │  target_type          │
                                       │  → BUILD              │
                                       │    (compile target)   │
                                       │  → VERIFY             │
                                       │    (validate output)  │
                                       └───────────────────────┘
```

### New Schema: `PlatformProfile`

```yaml
platform_profile:
  source_type: flutter           # what EXISTS — detected from filesystem
  target_type: static_website    # what to BUILD — detected from task + spec
  build_cmd: [npm, run, build]   # how to build the TARGET
  lint_cmd: [eslint, src/]       # how to lint the TARGET output
  output_globs:                  # what files must exist after build
    - "dist/index.html"
    - "dist/assets/**"
  forbidden_output_globs:        # what files must NOT be produced
    - "build/app/outputs/**"     # (flutter APK — wrong target!)
  validation:
    type: static_site_check
    checks:
      - html_valid: true
      - css_valid: true
      - no_broken_links: true
      - responsive: true
```

### Seven Changes to Adapt HERO to Any Platform

| # | Change | Why |
|---|--------|-----|
| 1 | Add `target_type` to project detection | Source type ≠ build target. A Flutter project can produce a website, docs, API, or APK. |
| 2 | Inject `PlatformProfile` into soldier context | Soldiers must know BOTH what's on disk (source) AND what to build (target). Currently only know source. |
| 3 | Pipeline stages split by source/target | PRE-COMMIT lints SOURCE. BUILD compiles TARGET. VERIFY validates TARGET output. Each stage needs the right type. |
| 4 | Add `post_build_validation` stage | After BUILD, verify output artifacts exist and match target type expectations. Currently missing entirely. |
| 5 | Add `task_intent_classifier` | Before soldiers spawn, classify the task: is this a website build? Docs update? Flutter feature? API endpoint? Routes validation accordingly. |
| 6 | Platform-specific stage overrides | `hero go --target website` should swap `flutter analyze` for `eslint`/`html-validate` in validation gates. |
| 7 | Soldier model routing by target type | Kimi K2.6 for Flutter/backend work. DeepSeek V4 Pro for web/frontend. Model lanes should consider target, not just role. |

---

## 3. SPECIFIC FIXES — Concrete Code Changes

### Fix 1: Soldier Prompt Architecture — Inject Target Context

**File:** `src/hero/soldier/context.py` → `build_context()`

```python
# CURRENT (broken)
def build_context(sandbox: SandboxData, task: str, 
                  cached_context: dict | None = None) -> str:
    # Injects: sandbox name, budget, katana, task
    # MISSING: platform, target_type, output expectations

# FIXED
@dataclass
class TargetProfile:
    """What the soldier should build, independent of what exists on disk."""
    platform: str              # "website", "flutter_app", "docs", "api"
    build_tool: str            # "npm", "flutter", "cargo", "mkdocs"
    output_dir: str            # "dist/", "build/web/", "site/"
    output_files: list[str]    # ["index.html", "assets/"] or ["app-release.apk"]
    validation: str            # "html-validate", "dart analyze", "pytest"

def build_context(sandbox: SandboxData, task: str, 
                  target: TargetProfile | None = None,
                  cached_context: dict | None = None) -> str:
    lines = [
        f"sandbox: {sandbox.name}",
        f"task: {task}",
    ]
    if target:
        lines += [
            f"target_platform: {target.platform}",
            f"target_build_tool: {target.build_tool}",
            f"target_output_dir: {target.output_dir}",
            f"target_must_produce: {', '.join(target.output_files)}",
            f"CRITICAL: You are building a {target.platform}. "
            f"Do NOT modify Flutter/Dart source files unless task explicitly requires it.",
        ]
```

**Impact:** Soldiers receive an explicit "you are NOT building a Flutter app, you are building a static website" signal. This prevents the context-confusion that caused both failures.

### Fix 2: Platform Detection — Separate Source from Target

**File:** `src/hero/commands/go.py` → new function `_detect_target_platform()`

```python
def _detect_target_platform(task: str, sandbox_path: Path) -> TargetProfile:
    """Determine WHAT to build from the task description, not from disk files.
    
    Returns a TargetProfile even if the project on disk is Flutter
    but the task says 'build a website'. Falls back to source_type
    only when task is ambiguous.
    """
    task_lower = task.lower()
    source_type = _detect_project_type(sandbox_path)["type"]
    
    # ── Task-based overrides (ordered by specificity) ──
    website_keywords = ["website", "landing page", "static site", "web page", 
                        "html", "css", "frontend site", "homepage"]
    docs_keywords = ["documentation", "docs site", "readme site", "mkdocs"]
    flutter_keywords = ["flutter app", "apk", "mobile app", "ios app", "widget"]
    api_keywords = ["api", "endpoint", "backend", "server", "rest"]
    
    if any(kw in task_lower for kw in website_keywords):
        return TargetProfile(
            platform="static_website",
            build_tool=_detect_web_build_tool(sandbox_path),
            output_dir="dist/",
            output_files=["index.html"],
            validation="static_site",
        )
    if any(kw in task_lower for kw in docs_keywords):
        return TargetProfile(
            platform="documentation",
            build_tool="mkdocs" if (sandbox_path / "mkdocs.yml").exists() else "npm",
            output_dir="site/",
            output_files=["index.html"],
            validation="static_site",
        )
    if any(kw in task_lower for kw in api_keywords):
        return TargetProfile(
            platform="backend_api",
            build_tool=_detect_backend_build_tool(sandbox_path),
            output_dir="dist/",
            output_files=["server.js", "index.js"],
            validation="api_tests",
        )
    
    # Fallback: assume target matches source
    if source_type == "flutter":
        return TargetProfile(
            platform="flutter_app",
            build_tool="flutter",
            output_dir="build/app/outputs/flutter-apk/",
            output_files=["app-release.apk"],
            validation="flutter",
        )
    # ... etc for other source types
```

**Impact:** Task intent determines build target. A Flutter project asked to "build a website" gets website tooling, not Flutter tooling.

### Fix 3: Validation Gates — Target-Aware, Not Source-Fixed

**File:** `src/hero/stages/pre_commit.py` → `_check_lint()`

```python
# CURRENT (broken)
def _check_lint(sandbox_path, verbose):
    project_type = _detect_project_type(sandbox_path)  # detects Flutter from pubspec.yaml
    if project_type == "flutter":
        cmd = ["dart", "analyze", str(sandbox_path)]   # ALWAYS runs dart analyze
    # ... even when the task was "build a static website"!

# FIXED
def _check_lint(sandbox_path, verbose, target_profile=None):
    project_type = _detect_project_type(sandbox_path)
    
    # If target_profile says "website", lint the website, not the Flutter source
    if target_profile and target_profile.platform == "static_website":
        cmd = _get_web_lint_command(sandbox_path)  # e.g., eslint, html-validate
    elif target_profile and target_profile.platform == "documentation":
        cmd = _get_docs_lint_command(sandbox_path)
    else:
        # Use source-based linting as before (Flutter → dart analyze)
        cmd = _get_source_lint_command(project_type)
```

**File:** `src/hero/stages/build.py` → `_check_build()`

```python
# FIXED: build command selected by TARGET, not SOURCE
def _check_build(sandbox_path, verbose, target_profile=None):
    if target_profile:
        cmd = _get_build_command_for_target(target_profile)
    else:
        cmd = _get_build_command_for_source(_detect_project_type(sandbox_path))
```

**Impact:** A website task runs `npm run build` + `eslint`, not `flutter build apk` + `dart analyze`. Wrong validator doesn't greenlight wrong output.

### Fix 4: Hero Go — Wire Target Into Pipeline

**File:** `src/hero/commands/go.py` → `go()` command

```python
# After Phase 1: Analysis
project = _detect_project_type(sandbox_path)

# NEW: Phase 1b: Target Detection
target = _detect_target_platform(task, sandbox_path)
click.echo(f"  Target platform: {target.platform}")
click.echo(f"  Target build:    {target.build_tool}")
click.echo(f"  Expected output: {target.output_dir}/{', '.join(target.output_files)}")

# Pass target through the pipeline
_ = _run_stage_safe(stage_name, sandbox_path, verbose=verbose,
                     target_profile=target)  # ← NEW parameter
```

**Impact:** Target profile propagates through all pipeline stages — PRE-COMMIT, BUILD, VERIFY all know what they're validating.

---

## 4. VALIDATION GATE DESIGN — Post-Build Output Verification

### The Missing Gate: `validate_output`

This gate runs AFTER the build stage and BEFORE verify. Its sole purpose: confirm the soldier produced the right kind of output.

```python
# File: src/hero/stages/validate_output.py (NEW)

def run_validate_output(sandbox_path: Path, target: TargetProfile, 
                         verbose: bool = False) -> dict:
    """Post-build output validation — did we build the RIGHT thing?
    
    This is the gate that would have caught both soldier failures:
    - Kimi (built nothing): output files missing → FAIL
    - DeepSeek (built wrong thing): output in wrong dir → FAIL
    """
    score = 100
    findings = []
    
    # ── Check 1: Required outputs exist ──
    for glob_pattern in target.output_files:
        output_path = sandbox_path / target.output_dir / glob_pattern
        matches = list(sandbox_path.glob(f"{target.output_dir}/{glob_pattern}"))
        if not matches:
            score -= 40
            findings.append({
                "severity": "error",
                "check": "output_exists",
                "message": f"Required output missing: {target.output_dir}/{glob_pattern} (-40)",
            })
    
    # ── Check 2: Forbidden outputs absent ──
    # (e.g., no APK in a website build — DeepSeek failure would be caught here)
    for forbidden in target.forbidden_outputs:
        forbidden_matches = list(sandbox_path.glob(forbidden))
        if forbidden_matches:
            score -= 30
            findings.append({
                "severity": "error", 
                "check": "forbidden_output",
                "message": f"Forbidden output detected for {target.platform} task: {forbidden} (-30)",
            })
    
    # ── Check 3: Content fingerprint ──
    # Verify output files aren't stale/empty
    for match in _find_output_files(sandbox_path, target):
        if match.stat().st_size < 100:  # suspiciously small
            score -= 20
            findings.append({
                "severity": "warning",
                "check": "output_size",
                "message": f"Output file suspiciously small: {match.name} ({match.stat().st_size} bytes)",
            })
    
    # ── Check 4: Platform-specific checks ──
    if target.platform == "static_website":
        score += _check_html_validity(sandbox_path, target, findings)
    elif target.platform == "flutter_app":
        score += _check_apk_exists(sandbox_path, target, findings)
    elif target.platform == "documentation":
        score += _check_docs_structure(sandbox_path, target, findings)
    
    return {
        "passed": score >= 70,
        "score": max(0, score),
        "status": "pass" if score >= 70 else ("warn" if score >= 50 else "fail"),
        "findings": findings,
    }
```

### Pipeline Integration

```
          PRE-COMMIT → BUILD → VALIDATE_OUTPUT → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
                                  ↑ NEW GATE ↑
                                  
          This gate answers: "Did we build the RIGHT thing?"
          - BUILD answers: "Did the build command succeed?"
          - VALIDATE_OUTPUT answers: "Did it produce the expected output FOR THIS TARGET?"
```

### Scoring Rubric for `validate_output`

| Check | Deduction | Catches |
|-------|-----------|---------|
| Required output file missing | -40 per file | Kimi K2.6 (built nothing) |
| Forbidden output detected | -30 per pattern | DeepSeek V4 Pro (built Flutter, not website) |
| Output file < 100 bytes | -20 per file | Stale/template output, empty builds |
| HTML validity (website target) | -10 per error | Broken HTML output |
| Missing asset directory | -15 | Incomplete website build |
| **Pass threshold:** ≥ 70 | | |

---

## 5. IMPLEMENTATION ROADMAP

| Phase | Changes | Files Affected | Priority |
|-------|---------|---------------|----------|
| **P0: Context Fix** | Add `TargetProfile` to `build_context()`, inject target into soldier | `context.py` | CRITICAL — fixes the root cause |
| **P1: Platform Detection** | Add `_detect_target_platform()`, wire into `go.py` Phase 1b | `go.py` | CRITICAL — enables target-aware routing |
| **P2: Output Validation** | New `validate_output.py` stage, add to pipeline ordering | `stages/validate_output.py`, `go.py` | CRITICAL — catches wrong-output failures |
| **P3: Gate Adaptation** | Target-aware lint/build in PRE-COMMIT and BUILD | `stages/pre_commit.py`, `stages/build.py` | HIGH — prevents wrong validator masking wrong output |
| **P4: Model Routing** | Soldier model selection considers target type | `spawner.py` | MEDIUM — optimization, not blocker |
| **P5: Stage Registry** | Platform profiles as configuration (YAML), not hardcoded | `config/platforms/*.yaml` | MEDIUM — extensibility |
| **P6: Tests** | Target detection, output validation, context injection | `tests/` | MANDATORY — all of the above |

### Minimum Viable Fix (P0-P2, ~200 lines)

This is the set of changes that would have prevented BOTH soldier failures:

1. **`context.py`**: `build_context()` now accepts optional `TargetProfile` and injects target hint into soldier prompt (~30 lines)
2. **`go.py`**: `_detect_target_platform(task, sandbox_path)` added, wired into Phase 1b (~60 lines)
3. **`stages/validate_output.py`**: New stage with output existence + content checks (~80 lines)
4. **`go.py`**: `validate_output` added to pipeline stage ordering after `build`, before `self_review` (~10 lines)

**Estimated effort:** 2-3 hours for the MVP fix. Full implementation (all phases): 1-2 days.

---

## 6. CONSENSUS & DISAGREEMENT

### Convergence (all 3 models agree)

1. **The root cause is context-design, not model-selection.** Both soldiers failed because the system injected Flutter project context for a website task. Fix the context, not the model lanes.
2. **Source/target separation is the architectural fix.** `_detect_project_type()` must be split into source_type (from files) and target_type (from task). Pipeline stages must route on target, not source.
3. **Post-build output validation is missing.** No gate checks "did the soldier produce the right kind of output?" This is a structural gap, not a model quality issue.
4. **The fix is small and surgical.** The MVP is ~200 lines across 3 files. The architecture doesn't need a rewrite — it needs one missing concept (target) threaded through existing plumbing.

### Minority View (MiMo V2.5 Pro)

MiMo notes that while the context fix is correct, the deeper issue is that **soldiers lack a "reality check" step** before they start building. MiMo proposes:

> Add a mandatory soldier step 0: "State what you understand the task to be, what you will build, and what you will NOT touch. Wait for confirmation before executing." This would have caught both failures because Kimi would have paused at "I'm exploring a Flutter codebase" and DeepSeek would have stated "I'm updating existing Flutter documentation" — both of which contradict the actual task.

This minority view is preserved at `COUNCIL_ALTERNATIVES_PLATFORM_FAILURE.toon` for future reference. The council consensus is that the "reality check" step adds latency and is best addressed by fixing the context injection, which makes the soldier's understanding correct from the start.

---

## DECISION

**Adopt source/target separation in the pipeline.** Implement P0-P2 immediately (context fix + platform detection + output validation). P3-P6 follow as enhancements.

**RATIONALE:** 3/3 models agree on root cause. The fix is ~200 lines in 3 files. Post-build output validation catches this class of error regardless of model or task.

**NEXT ACTION:** Lead to dispatch a soldier to implement P0-P2 on the HERO codebase itself.
