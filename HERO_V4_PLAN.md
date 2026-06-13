# HERO v4 — Multi-Agent Pipeline Evolution

> **Planned at:** commit `bc28b43`, 2026-06-13  
> **Author:** Council deliberation (MiMo V2.5 Pro)  
> **Status:** DESIGN — pending approval

---

## 1. Motivation

HERO currently runs 8 pipeline stages: `navigate → pre_commit → build → harden → legal → cipr → verify → archive`. These catch basic issues but don't leverage advanced agent skills (addyosmani TDD, shadcn/improve) or production-hardening gates (encryption audit, APK protection, anti-AI detection).

HERO v4 adds **4 new stage groups** that slot into the existing pipeline without breaking any existing stage:

```
navigate → pre_commit → build → tdd-audit → improve-audit → harden+ → anti-ai → plan-gen → verify → archive
```

---

## 2. New Stage Definitions

### Stage 9: `tdd-audit` (after build, before verify)

**Source skill:** addyosmani/test-driven-development  
**Integration method:** Inline the full SKILL.md into a soldier prompt  
**What it checks:**
- RED→GREEN→REFACTOR compliance for recent changes
- Beyoncé Rule violations (changed code with no corresponding test)
- Test pyramid balance (80/15/5)
- Anti-pattern detection in test files (flaky tests, snapshot abuse, over-mocking)
- Test size classification (small/medium/large)

**Soldier task:** Run the addyosmani TDD skill against the worktree. Check all changed files (`git diff --name-only`) and flag any production code change without a corresponding test change. Report test quality violations.

**Output:** `findings[]` — each with category `test_gap`, `beyonce_violation`, `test_quality`

**Config in pipeline manifest:**
```json
{
  "stage": "tdd-audit",
  "soldier_model": "step-3.7-flash",
  "timeout": 300
}
```

### Stage 10: `improve-audit` (parallel to tdd-audit)

**Source skill:** shadcn/improve  
**Integration method:** Inline the full SKILL.md + references/audit-playbook.md into a soldier prompt  
**What it checks:**
- Full codebase audit across 9 categories (correctness, security, perf, tests, tech debt, deps, DX, docs, direction)
- Hotspot-weighted (churn + criticality)
- Outputs prioritizing table (impact ÷ effort)

**Soldier task:** Run the improve workflow against the codebase: recon → audit → vet → plan. Write plans to `plans/` directory in the worktree.

**Output:** `findings[]` with full shadcn/improve finding format + `plans/NNN-*.md`

**Config:**
```json
{
  "stage": "improve-audit",
  "soldier_model": "step-3.7-flash",
  "timeout": 600,
  "effort": "quick"
}
```

### Stage 11: `harden+` (replaces/extends harden)

**Extends** the existing `harden` stage. Adds:

| Check | Tool/Skill | Source |
|-------|-----------|--------|
| Legal compliance | SPDX header scan, OSS license allowlist | Existing `legal` stage logic |
| Encryption audit | Hardcoded keys, missing runtime decryption | Custom regex patterns |
| Obfuscation check | ProGuard/R8 status, string readability | Custom patterns |
| APK protection | Root detection, tamper check, signature verify | Custom shell checks |
| Dependency audit | `flutter pub outdated`, `npm audit` | Existing cipr logic |

**Design:** `harden+` runs as a superset of the current `harden` stage. The old `harden` and `legal` stages remain for backward compat; `harden+` can be gated behind `--hard` flag.

**Config:**
```json
{
  "stage": "harden+",
  "checks": ["legal", "encryption", "obfuscation", "apk", "deps"],
  "block_on": ["critical", "error"]
}
```

### Stage 12: `anti-ai` (new)

**Problem:** AI-generated code often shares patterns — generic Material Icons, identical widget structures, boilerplate naming, predictable comment styles.

**What it checks:**
- Generic Material icons vs custom SVG assets (`Icons.*` in widget tree — flag if no custom alternative exists)
- AI boilerplate comments (`// TODO: Implement`, generated doc comment patterns)
- Uniform widget structure repetition (identical ListTile/Container trees repeated >3x)
- Generic asset naming (`icon_1.svg`, `image_2.png`)
- Missing custom illustration assets in screens

**Soldier task:** Scan `lib/` for each pattern, generate a report.

**Output:** `findings[]` with category `anti_ai`

**Config:**
```json
{
  "stage": "anti-ai",
  "thresholds": {
    "max_generic_icons": 5,
    "max_identical_widgets": 3,
    "min_custom_assets": 2
  }
}
```

### Stage 13: `plan-gen` (post-processing, always last)

**Not a soldier stage** — runs locally in the pipeline executor.  
**Input:** All findings from all previous stages  
**Process:**
1. Deduplicate findings across gates (same file+line+rule)
2. Sort by severity (critical → error → warn → info)
3. Group by file
4. Write `plans/INDEX.md` with priority-sorted fix tasks
5. Optionally: `gh issue create` for each critical finding

**Output:** `plans/INDEX.md` + optional GitHub issues

---

## 3. Pipeline Mode Mapping

New modes for `hero go --mode`:

| Mode | Stages | When to use |
|------|--------|-------------|
| `quick` | navigate → pre_commit → build | Daily dev, fast feedback |  
| `ci` | pre_commit → build → cipr | CI pipeline |
| `full` | All 13 stages | Pre-release, full audit |
| `audit` | navigate → improve-audit → plan-gen | Deep codebase review |
| `ship` | All stages + harden+ + anti-ai | Before release build |
| `tdd` | tdd-audit → plan-gen | TDD compliance check |

---

## 4. CLI Changes

```bash
hero go --mode ship --sandbox X --task "ship FeyaPDF v2"   # Full release pipeline
hero go --mode audit --sandbox X --task "deep review"       # Codebase audit only
hero go --mode tdd --sandbox X --task "check tests"         # TDD compliance
hero go --stage improve-audit --sandbox X                   # Single stage
hero go --stage tdd-audit,anti-ai --sandbox X               # Multiple stages
```

New flags:

```bash
--hard           # Enable harden+ instead of basic harden
--gh-issues      # Publish critical findings as GitHub issues
--plan-only      # Run plan-gen without other stages (regenerate from last report)
```

---

## 5. Implementation Plan

| Phase | What | Effort | Risk |
|-------|------|--------|------|
| **1** | `plan-gen` stage — merge findings schema, dedup, write INDEX.md | S | LOW |
| **2** | `tdd-audit` stage — addyosmani TDD skill in soldier prompt | S | LOW |
| **3** | `improve-audit` stage — shadcn/improve skill in soldier prompt | S | MED (token cost) |
| **4** | `harden+` stage — encryption, obfuscation, APK checks | M | MED |
| **5** | `anti-ai` stage — icon/widget/boilerplate detection | S | LOW |
| **6** | New modes (`ship`, `audit`, `tdd`) + CLI flags | S | LOW |
| **7** | Integration test suite — mock pipeline with all stages | M | MED |

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Soldier token budget blown (improve-audit is expensive) | Default `effort: quick`; `--deep` flag for full pass |
| addyosmani/improve skill drifts from upstream | Pin to specific git SHA, add drift check in plan-gen |
| tdd-audit false positives on test-less config files | Config-only changes are already in addyosmani's "when NOT to use" |
| anti-ai false positives (custom code that looks generic) | Threshold-based, warn not block |
| Pipeline too slow for CI | `ci` mode stays unchanged; new stages only in `full`/`ship` modes |

---

## 7. Does Not Break

- All existing `hero go` commands continue working
- Existing `hero pre-commit` / `hero build` / etc. unchanged
- Existing `--skip`, `--verify`, `--archive` flags unchanged
- Backward compatible: new stages are opt-in via mode or `--stage`
