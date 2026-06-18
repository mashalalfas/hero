# COUNCIL READINESS REPORT — HERO System Platform Blindness Fix Assessment

**Council convened:** 2026-06-18  
**Assessed changes:** P0-P2 structural fix (TargetProfile, _detect_target_platform, validate_output)  
**Reference:** COUNCIL_DIAGNOSIS_PLATFORM_FAILURE.md

---

## Summary Verdict

**READY_WITH_CAVEATS** — The architectural foundation (TargetProfile, context separation, output validation gate) is correct and solid. However, the **target variable is never wired into the pipeline execution loop**, making validate_output a no-op and leaving the original failure mode unmitigated in production runs. Two additional gaps (skill card injection, multi-platform project handling) need addressing before the system can be considered fully ready.

---

## 1. Is the Structural Fix Complete?

**Not yet. The fix chain has a broken link.**

### Walkthrough of the Fix Chain

| Step | Status | Detail |
|------|--------|--------|
| **① TargetProfile dataclass** (`context.py`) | ✅ **Done** | Dataclass with `platform`, `build_tool`, `output_dir`, `output_files`, `validation` fields. Clean separation of source from target intent. |
| **② build_context(target=...)** (`context.py`) | ✅ **Done** | Injects `target_platform`, `target_build_tool`, `target_output_dir`, `target_must_produce`, and a CRITICAL hint: "You are building a {platform}. Do NOT modify source files unless task explicitly requires it." |
| **③ _detect_target_platform(task, sandbox_path)** (`go.py:788`) | ✅ **Done** | Keyword-based classifier: website, docs, flutter, api fallthroughs + source-matching fallback. Wired into go() Phase 1b with echo output (line 839). |
| **④ validate_output stage** (`stages/validate_output.py`) | ✅ **Done** | Checks: output exists (-40), forbidden outputs absent (-30), file not too small (-20). Pass ≥ 70. Fast path when `target` is None/empty. |
| **⑤ validate_output in stage ordering** (`go.py:71,82,84,85`) | ✅ **Done** | `"validate_output"` added to all mode stage lists after `"build"`. |
| **⑥ _run_stage_safe plumbing** (`go.py:126-130`) | ✅ **Done** | Correctly routes `target` kwarg: `target=kw.get("target", {})` |
| **⑦ Target passed into pipeline loop** (`go.py:1128-1185`) | ❌ **NOT WIRED** | The pipeline execution loop calls `_run_stage_safe(name, sandbox_path, verbose=verbose)` **without `target=target`**. The `target` variable is captured on line 839 but never flows into any stage call. |

### The Broken Link

```python
# Line 839: target is correctly detected
target = _detect_target_platform(task, sandbox_path)

# Lines 1154-1161: pipeline loop ignores target entirely
else:
    result = _run_stage_safe(
        stage_name, sandbox_path, verbose=verbose,  # ← target MISSING
    )
```

**Consequence:** Every call to `run_validate_output` receives `target={}` (via `kw.get("target", {})`), which triggers the fast path:
```python
if not target:
    return {"passed": True, "score": 100, "status": "pass", "findings": []}
```

**Result:** validate_output always passes with a perfect score. The original failure scenario (Flutter project + "build website" task) would still go uncaught.

### What Would Need to Happen to Fix It

One line change in the pipeline execution loop:

```python
# Current (broken)
result = _run_stage_safe(stage_name, sandbox_path, verbose=verbose)

# Fixed
result = _run_stage_safe(stage_name, sandbox_path, verbose=verbose, target=target)
```

This would pass the TargetProfile dict into validate_output's `target` parameter, making all three checks active:
- **Missing outputs** → catches Kimi's "built nothing" failure (-40 each)
- **Forbidden outputs** → catches DeepSeek's "built Flutter APK in website task" failure (-30 per pattern)
- **Suspiciously small files** → catches empty/stale builds (-20 each)

---

## 2. Gaps Remaining

### 🔴 GAP P0: Target not passed to pipeline stages (CRITICAL)

As documented above. Validates all day long, but it's a whisper in a vacuum — nobody listens because the message never arrives.

- **Severity:** CRITICAL — renders the entire validate_output gate inert
- **Fix:** Pass `target=target` to `_run_stage_safe()` in the pipeline loop and the self_review/archive special cases
- **Location:** `go.py` lines 1154-1161 (the `else` branch), and similarly for `self_review` and `archive` stages

### 🔴 GAP P1: validate_output also needs target in `pre_commit` and `build` stages

The diagnosis correctly identified that PRE-COMMIT should lint the **target** (not source) when building a website from a Flutter project. However:

- `run_pre_commit` is called without `target` (line 1154-1161)
- `run_build` is called without `target` (line 1154-1161)
- The build stage lambda only passes `bump` kwarg, not target

If the soldier builds a website, PRE-COMMIT will still run `dart analyze` on the Flutter codebase — the wrong linter for the task.

- **Severity:** HIGH — validation gate is inert, but the build tool itself still works (npm build succeeds regardless)
- **Fix:** Wire `target` into pre_commit and build stage calls, and add target-aware lint/build selection

### 🟡 GAP P2: Ambiguous tasks fall back to source detection

`_detect_target_platform` falls back to source type for many tasks:

```python
# Only these are explicit:
website_keywords, docs_keywords, flutter_keywords, api_keywords

# Everything else → falls through to source detection
```

Tasks like:
- "Create interactive landing page with animations" → might not match `website_keywords`
- "Design a REST API for user management" → matches `api_keywords` (OK)
- "Build the UI components" → ambiguous, falls back to source
- "Add a dark mode" → ambiguous, falls back to source

- **Severity:** MEDIUM — many tasks will correctly match, but edge cases fall through to old behavior
- **Potential fix:** Expand keyword lists, or add a `--target` CLI flag for explicit override

### 🟡 GAP P3: web-designer role skill cards NOT injected

The web-designer role exists in `army.yaml` with `step-3.7-flash` and `64K` context window. Skill cards exist at `skills/web-design/SKILL_CARDS.md` (GSAP, Three.js, Parallax/Lenis, Motion, Tailwind, WebGL, a11y, perf — 9 cards).

However:
```bash
$ grep -rl "web-designer\|skill_cards\|SKILL_CARDS" src/hero/
# No results
```

No code loads the skill cards or injects them into soldier context. The `build_context()` function accepts `cached_context` but nothing populates it with skill card data for the web-designer role.

- **Severity:** MEDIUM — the role can be dispatched but soldiers won't have web-design-specific knowledge
- **Fix:** Add a `load_skill_cards(role_name, sandbox_path)` function that reads `skills/{role}/SKILL_CARDS.md`, called during context building when the dispatched role matches
- **Location:** `context.py` or `spawner.py` in the role→context mapping

### 🟢 GAP P4: Multi-platform projects and monorepos

No existing support for:
- A monorepo with both a Flutter app and a website sub-project
- Projects that produce multiple output types (e.g., API + docs)
- The `--target` CLI flag mentioned in the council diagnosis isn't implemented

- **Severity:** LOW — the architecture supports this cleanly now (TargetProfile is the foundation), but no plumbing exists for explicit override or multi-target pipelines
- **Fix:** Add `--target` CLI flag to `hero go` that overrides `_detect_target_platform`; add `--multi-target` for multiple concurrent builds

### 🟢 GAP P5: validate_output works for non-website projects

The validate_output stage is **platform-agnostic** by design. It uses the `target` dict, which can be configured for any platform. The forbidden output patterns are tracked per-platform in `_FORBIDDEN_OUTPUTS`. Missing patterns for `documentation` and `backend_api` (both return `[]`) reduce its value for those platforms.

However, since target is never passed (GAP P0), this question is currently academic.

- **Severity:** LOW — the architecture is correct, just needs target wiring
- **Note:** For flutter_app targets, forbidden outputs prevent `dist/**` and `site/**` — which is correct

---

## 3. Is HERO Ready for Any Project?

### Assessment Matrix

| Scenario | Ready? | Why |
|----------|--------|-----|
| **Flutter project → build website** | ❌ | validate_output is inert; target not wired |
| **Node project → build backend API** | ✅ | Source = Node, target = backend_api, same tooling |
| **Node project → build docs site** | ⚠️ | Target detected, but validate_output inert |
| **Python project → build API docs** | ⚠️ | Ambiguous task may miss keyword match |
| **Monorepo (Flutter + web)** | ❌ | No multi-target support, target detection uses one sandbox_path |
| **New project, no package manager** | ❌ | Source detection returns "unknown" → target fallback returns all-empty |
| **New project → build landing page** | ⚠️ | Works if task contains "website" or "landing page" keywords |
| **Flutter project → build Flutter app** | ✅ | Source matches target, both say Flutter |

### Readiness Rating: READY_WITH_CAVEATS

**The architectural foundation is solid.** The council diagnosis was correct, and the implemented changes (TargetProfile, _detect_target_platform, validate_output) are the right abstractions. The code is clean, well-typed, and properly documented.

**But one line keeps it from working:** `target=target` is never passed to the pipeline stages. This single omission cascades:

1. validate_output always passes → no gate catches wrong/missing output
2. build stage lacks target awareness → wrong build tool on mixed projects
3. pre_commit lacks target awareness → wrong linter on mixed projects
4. soldier context building is ready but unused (build_context receives target in spawner but pipeline stages don't pass it through)

**Fixing this is a one-line change** (plus propagating `target` to the archive and self_review special cases for consistency). After that:

- The Flutter+website scenario is caught
- validate_output activates with real scoring
- The fix chain is complete

---

## 4. Gap List (Ranked by Severity)

| # | Severity | Gap | Fix | File | Lines |
|---|----------|-----|-----|------|-------|
| P0 | 🔴 CRITICAL | `target` not passed to pipeline stages → validate_output inert | Pass `target=target` to all `_run_stage_safe()` calls | `go.py` | 1154-1161 |
| P1 | 🔴 HIGH | pre_commit/build stages lack target awareness for lint/build selection | Wire target into stage lambdas | `go.py` | 122-131 |
| P2 | 🟡 MEDIUM | Ambiguous tasks fall back to source detection | Expand keywords or add `--target` CLI flag | `go.py` | 788-850 |
| P3 | 🟡 MEDIUM | web-designer skill cards never injected | Load SKILL_CARDS.md into soldier context payload | `context.py` / `spawner.py` | — |
| P4 | 🟢 LOW | No multi-platform/monorepo support | `--target` flag, multi-target pipeline | `go.py` | — |
| P5 | 🟢 LOW | validate_output missing forbidden patterns for docs/api | Add patterns to `_FORBIDDEN_OUTPUTS` | `validate_output.py` | 37-42 |

---

## 5. #1 Thing to Fix Next

### 🔴 Fix P0: Wire `target` into the pipeline execution loop

**File:** `/home/max/Development/HERO/src/hero/commands/go.py`  
**Location:** Lines 1148-1165 (the `for (stage_name,) in _stage_list:` loop)

**Change:** Pass `target=target` to every `_run_stage_safe()` call. The `target` variable is already available (line 839).

```python
# Before (lines 1154-1161)
else:
    result = _run_stage_safe(
        stage_name, sandbox_path, verbose=verbose,
    )

# After
else:
    result = _run_stage_safe(
        stage_name, sandbox_path, verbose=verbose,
        target=target,
    )
```

Also fix the `self_review` and `archive` special cases to pass `target` for consistency.

**Impact:** This single change activates the entire validate_output gate, enables target-aware lint/build selection (when P1 is also wired), and completes the fix chain described in the council diagnosis. The Flutter-context-contaminates-website-build failure is fully mitigated.

**Effort:** ~3 lines changed. 30 seconds of work. 100% of the gap-closing impact.

---

## Appendix: File State Summary

| File | State | Role |
|------|-------|------|
| `context.py` | ✅ Complete | TargetProfile dataclass + build_context(target=...) |
| `go.py` | ⚠️ Target detected but not wired | `_detect_target_platform` works (line 839), but pipeline loop doesn't pass it |
| `validate_output.py` | ✅ Complete but inert | Correct implementation, but receives empty target → always passes |
| `COUNCIL_DIAGNOSIS_PLATFORM_FAILURE.md` | ✅ Complete | Correct diagnosis, correct prescription, implementation mostly done |
| `army.yaml` | ⚠️ web-designer role registered, skill cards on disk, no injection code | Role exists, cards exist, but nothing loads them |
| `skills/web-design/SKILL_CARDS.md` | ✅ Complete | 9 well-structured cards (GSAP, Three.js, Parallax, Motion, Tailwind, WebGL, a11y, perf) |
