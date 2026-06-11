# HERO Council Report — Full Pipeline Rebuild Plan
**Date:** 2026-05-31  
**Council:** Kimi 2.6 (Analyst) + GLM 5.1 (Reasoner) + MiMo Pro (Synthesis)  
**Subject:** Rebuilding the HERO pipeline to implement the boss-approved architecture  
**Status:** VERDICT REACHED — implementation plan below

---

## Section 1 — Convergence (Points of Full Agreement)

All three analysts agree on the following:

### 1.1 The Scoring Foundation Is Solid
`hero score` (23/23 tests passing) is the correct foundation. Every pipeline stage must call it after execution, record the score in the manifest, and gate on thresholds. No disagreement here.

### 1.2 Execution Line Is Non-Negotiable
Pre-commit → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE is the mandatory execution line. Early planning phases (Council → Research → PE → Architect → Lead) are bypassable. No disagreement.

### 1.3 Solo Work Is Never Allowed
Every execution step must spawn a soldier. The communicator routes; it never executes. This is the ethic.

### 1.4 `hero go` Is the Orchestrator
`hero go` must be redesigned as the single entry point that sequences the execution line, calls `hero score` between stages, gates on scores, and delegates all actual work to soldiers.

### 1.5 The Build Order Is Clear
Score exists → Build stage commands (already in `score.py`) → Wire stages into `go.py` → Update `cli.py` → Update config → Write legal skill. Sequential dependency, no parallelization possible at the architecture level.

### 1.6 LEGAL Phase Scope
The council report on LEGAL (`COUNCIL_REPORT_LEGAL_PHASE.md`) is the authoritative spec for LEGAL. The integration plan here defers to that report for artifact details and uses its legal-config.json schema.

---

## Section 2 — Disagreements (Resolved)

### Disagreement A: Where Does `hero score` Get Called?

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | `hero score` should be called **inside each soldier's task** | "Each soldier runs its stage and self-scores. The pipeline just collects scores. Decentralized, resilient." |
| **GLM 5.1** | `hero score` should be called **by `hero go` between stages** | "The orchestrator must control gating logic. If soldiers self-score, a failing stage might report 100 and block the pipeline from knowing. Centralized control." |
| **MiMo Pro** | **GLM's approach with a fallback** | "Orchestrator calls `hero score` after each stage returns. If a soldier crashes before scoring, the orchestrator runs the scorer itself as a no-op. Best of both." |

**Resolution:** Orchestrator (`hero go`) calls `hero score` after each stage. Each soldier task brief includes "Run `hero score --pipeline <stage> --sandbox <name>` and record output." If the soldier fails to produce a score, the orchestrator runs it. The manifest records both the soldier's self-report and the orchestrator's verification score.

### Disagreement B: Bypass Rules — Who Decides?

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | User decides via `--full` flag | "`hero go --full` runs all phases; default skips planning phases. User is in control." |
| **GLM 5.1** | `hero go` auto-detects from task description | "Users shouldn't need to know pipeline internals. `hero go` should inspect the task and decide. 'fix typo' → skip Council; 'redesign auth' → full pipeline." |
| **MiMo Pro** | **Hybrid: auto-detect with override** | "Auto-detect by default (GLM). `--full` and `--skip` flags allow override (Kimi). `--full` forces all phases; `--skip Council,Research` explicitly bypasses." |

**Resolution:** Hybrid. `hero go` auto-detects bypass eligibility from task complexity/size. Flags: `--full` (force all phases), `--skip <phase1,phase2>` (explicit bypass), `--no-bypass` (disable auto-bypass, run everything).

### Disagreement C: What Constitutes a "Stage" in the Manifest?

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | Stages are **tool invocations** (gitleaks run, eslint run, etc.) | "A stage is a concrete action with a tool and exit code. The manifest records tool outputs." |
| **GLM 5.1** | Stages are **soldier tasks** (each stage is a dispatched soldier) | "A stage is a soldier with a role. The soldier decides which tools to run. The pipeline just tracks soldier completion." |
| **MiMo Pro** | **Both: soldier task with embedded tool commands** | "Stage = soldier dispatch. Soldier brief includes specific tool invocations. Manifest records both: soldier status AND tool outputs." |

**Resolution:** Stages are soldier dispatches. Each soldier brief includes the exact tool commands to run (e.g., "Run `gitleaks detect`, `eslint .`, record output"). The manifest records soldier status AND extracted tool metrics for scoring.

---

## Section 3 — Verdict: Numbered Build Phases

### Phase 0 — Foundation (Already Complete)
- `hero score` command: 23/23 tests passing ✅
- Scoring rubrics for all 7 execution-line stages implemented
- Score thresholds: ≥70 pass, 50-69 warn, <50 fail

### Phase 1 — Stage Command Modules (Sequential, ~2 days)
Build one module per stage. Each module encapsulates the tool invocations for that stage.

**Order and rationale:**

```
Phase 1a: pre_commit.py   (no dependencies — standalone tool invocations)
Phase 1b: build.py        (depends on: project detection logic from score.py)
Phase 1c: harden.py       (depends on: build output paths from build.py)
Phase 1d: legal.py        (depends on: nothing new — uses legal-templates repos)
Phase 1e: cipr.py         (depends on: build artifacts from build.py)
Phase 1f: verify.py       (depends on: all other stages — composite)
Phase 1g: archive.py      (depends on: all stages complete)
```

**Why this order:** Each stage module must exist before `go.py` can call it. Stages with no upstream dependencies (pre_commit, legal) can be built first. Stages that consume other stages' outputs (harden, cipr, verify) must come after.

**Complexity:** Low for each module. They are thin wrappers around subprocess calls to existing tools (gitleaks, eslint, flutter build, etc.). The scoring logic already exists in `score.py`; these modules extract the same signals but produce structured stage output.

### Phase 2 — `hero go` Redesign (Sequential, ~3 days)
`go.py` must be rewritten to:
1. Accept new flags: `--full`, `--skip`, `--no-bypass`, `--stage <name>` (for running a single stage)
2. Auto-detect bypass eligibility from task description
3. For each execution-line stage:
   - Spawn a soldier (never execute directly)
   - Wait for soldier completion
   - Call `hero score --pipeline <stage>` 
   - Record score in manifest
   - Gate: ≥70 proceed, 50-69 warn+proceed, <50 block+re-queue
4. Update manifest schema to include per-stage scores
5. Wire into `PipelineExecutor` for the execution loop

**Complexity:** Medium. This is the most complex single file change. It touches dispatch, soldier spawning, scoring, manifest management, and the verify/fix loop.

### Phase 3 — Integration Changes (Parallel-safe, ~1 day)
- **`cli.py`:** No structural changes needed — all new commands are in existing modules. `go.py` import already exists.
- **`config.yaml`:** Add pipeline stage definitions under a `pipeline:` key:
  ```yaml
  pipeline:
    execution_line:
      - pre-commit
      - build
      - harden
      - legal
      - cipr
      - verify
      - archive
    bypassable_phases:
      - council
      - research
      - prompt-engineer
      - architect
      - lead
    score_thresholds:
      pass: 70
      warn: 50
      fail: 50
    always_spawn: true
  ```
- **`army.yaml`:** Add role entries for new soldier archetypes:
  - `security-scanner` — runs gitleaks, semgrep, trivy
  - `legal-officer` — runs license-checker, SBOM generation, EULA templating
  - `build-engineer` — runs build commands with obfuscation flags
- **`PIPELINE.md`:** Update diagram to reflect new stage order

**Complexity:** Low. Config edits and documentation.

### Phase 4 — Legal-Compliance Skill (Sequential, ~1 day)
Create `~/.agents/skills/legal-compliance/SKILL.md` per the spec in Section 5 below.

**Complexity:** Low. Thin orchestrator skill following the spec-driven-development pattern.

### Phase 5 — Testing & Validation (Sequential, ~1 day)
- End-to-end test: `hero go --sandbox HERO --task "test pipeline" --dry-run`
- Verify manifest schema includes all stage scores
- Verify gating logic: inject a failing score, confirm pipeline blocks
- Verify bypass logic: `hero go --skip Council,Research` for a small task
- Verify legal skill: run on Melody_MD, confirm EULA + Privacy Policy generated

**Complexity:** Medium. Requires actual tool binaries (gitleaks, eslint, etc.) to be installed.

---

## Section 4 — Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 0: FOUNDATION (DONE)                    │
│  hero score — 23/23 tests ✅                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            │            ▼
    ┌─────────────────┐    │    ┌──────────────────┐
    │ pre_commit.py   │    │    │ legal.py          │
    │ (no deps)       │    │    │ (legal-templates) │
    └────────┬────────┘    │    └────────┬─────────┘
             │              │             │
             ▼              │             ▼
    ┌─────────────────┐    │    ┌──────────────────┐
    │ build.py        │    │    │ cipr.py           │
    │ (score.py logic)│    │    │ (depends: build)  │
    └────────┬────────┘    │    └────────┬─────────┘
             │              │             │
             ▼              │             ▼
    ┌─────────────────┐    │    ┌──────────────────┐
    │ harden.py       │    │    │ verify.py         │
    │ (depends: build)│    │    │ (depends: ALL)    │
    └────────┬────────┘    │    └────────┬─────────┘
             │              │             │
             └──────────────┼─────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ archive.py        │
                  │ (depends: ALL)    │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PHASE 2: go.py   │
                  │ (wires all)      │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PHASE 3: config  │
                  │ army.yaml update │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PHASE 4: skill   │
                  │ legal-compliance │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PHASE 5: test    │
                  └──────────────────┘
```

**Parallelization opportunities:**
- `pre_commit.py` and `legal.py` can be built in parallel (no inter-dependency)
- `build.py` can start once `pre_commit.py` scaffolding is confirmed
- `config.yaml` edits, `army.yaml` updates, and `PIPELINE.md` rewrite can happen in parallel with module builds
- Legal skill (Phase 4) can start as soon as LEGAL phase spec is confirmed (it already is, from the council report)

---

## Section 5 — Stage Implementation Plan

### 5.1 PRE-COMMIT Stage

**Purpose:** Catch secrets and lint errors before code enters the pipeline.

**Tools invoked:**
- `gitleaks detect --source <path> --no-git` (or `--staged` for pre-commit hook)
- `eslint .` with `eslint-plugin-security` rules (Node/React projects)
- `flutter analyze` (Flutter projects)
- `ruff check .` (Python projects)
- Copyright header check (all projects)

**Files created/modified:**
- `.pre-commit-config.yaml` (if not present) — adds gitleaks hook
- No source file modifications (read-only scan)

**Scoring rubric (feeds `hero score --pipeline pre-commit`):**
| Check | Weight | Deduction |
|-------|--------|-----------|
| Secrets found (gitleaks) | Critical | -30 per secret |
| Lint errors | High | -10 per error |
| Lint warnings | Medium | -5 per warning |
| Missing copyright headers | Low | -2 per file |

**Soldier expertise:** `security-scanner` role — fast, tool-running soldier. No reasoning needed.

**Bypass condition:** Small mechanical tasks (typo fixes, doc updates) where no source code changes are made.

---

### 5.2 BUILD Stage

**Purpose:** Compile the project with hardening flags. Produce build artifacts.

**Tools invoked:**
- `flutter build apk --obfuscate --split-debug-info=build/debug-info` (Flutter)
- `npm run build` (Node/React) 
- `python -m build` (Python)
- `cargo build --release` (Rust)

**Files created/modified:**
- `build/` directory (Flutter debug-info, APK/AAB)
- `dist/` directory (Node)
- `.obfuscate` marker file (for HARDEN to verify)
- `build-report.json` (stage output for scoring)

**Scoring rubric:**
| Check | Weight | Deduction |
|-------|--------|-----------|
| Build succeeded | Critical | -20 if failed |
| Obfuscation flag present | High | -15 if missing (Flutter) |
| ProGuard/R8 enabled | High | -15 if missing (Android) |
| Debug symbols in release | Medium | -15 if present |

**Soldier expertise:** `build-engineer` role — knows build toolchains per project type.

**Bypass condition:** Pre-SHIP only — skipped for local dev builds unless `--full` flag set.

---

### 5.3 HARDEN Stage

**Purpose:** Apply and verify security hardening beyond compilation.

**Tools invoked:**
- `trivy fs .` (dependency vulnerability scan)
- `semgrep --config=auto .` (SAST for JS/TS/Ruby)
- `osv-scanner --lockfile pubspec.lock` (Dart deps — Flutter only)
- `socket scan` (supply chain malware check)
- Root/jailbreak detection: verify `flutter_jailbreak_detection` or equivalent in source
- Certificate pinning: verify config in source
- `confidential` package: verify sensitive strings are obfuscated (Flutter)

**Files created/modified:**
- `security/trivy-report.json`
- `security/semgrep-report.json`
- `security/osv-report.json` (Flutter)
- `security/harden-report.json` (stage output)
- Source files: inject root detection if missing (soldier modifies)
- Source files: inject cert pinning if missing (soldier modifies)

**Scoring rubric:**
| Check | Weight | Deduction |
|-------|--------|-----------|
| Trivy: no CRITICAL CVEs | Critical | -30 per CRITICAL |
| Semgrep: no high-severity findings | High | -20 per high |
| OSV: no Dart vulns | High | -20 per Dart CVE |
| Socket: no malicious packages | Critical | -40 if found |
| Obfuscation verified | High | -20 if missing |
| Debug symbols stripped | Medium | -15 if present |
| Root detection present | Medium | -10 if missing |
| Cert pinning present | Medium | -10 if missing |

**Soldier expertise:** `security-scanner` role — knows all 7 P0/P1 tools from security-integration README.

**Bypass condition:** Never bypassed on CI. Local dev: skip if `--skip harden` passed. Mandatory before SHIP.

---

### 5.4 LEGAL Stage

**Purpose:** Generate legal artifacts and enforce license compliance.

**Tools invoked:**
- `npx license-checker --production --json` → `legal/license-scan.json`
- `npx @cyclonedx/cyclonedx-npm` or `spdx-tools` → SBOM generation
- `npx spdx-tools validate` → SBOM validation
- EULA generation: Commercial-Standard-License template → `legal/EULA.md`
- Privacy Policy: openterms `appPrivacy` → `legal/PRIVACY.md`
- ToS: openterms `appTerms` → `legal/TOS.md` (if hasAccounts)
- Copyright header injection: SPDX identifiers in source files
- App Store checklist generation: `legal/app-store-checklist.md`

**Files created/modified:**
- `legal/EULA.md`
- `legal/PRIVACY.md`
- `legal/TOS.md` (conditional)
- `legal/SBOM.spdx` or `legal/SBOM.json` (CycloneDX)
- `legal/license-scan.json`
- `legal/LEGAL_GATE_REPORT.md` (pass/fail + evidence)
- `legal-config.json` (project config, created if missing)
- Source files: copyright headers injected by soldier

**Scoring rubric:**
| Check | Weight | Deduction |
|-------|--------|-----------|
| No blocked licenses (GPL/AGPL/SSPL) | Critical | -30 per blocked license |
| SBOM generated + validated | High | -20 if missing/invalid |
| EULA present | High | -20 if missing |
| Privacy Policy present | High | -15 if missing |
| Copyright headers on source files | Medium | -2 per file missing |
| App Store checklist complete | Low | -10 if incomplete |

**Soldier expertise:** `legal-officer` role — runs license tools, templates EULA/PP, generates SBOM.

**Bypass condition:** Bypassable for local dev. Mandatory on CI and before SHIP. Fast path for dependency-only changes (skip EULA/PP regeneration).

---

### 5.5 CI/PR Stage

**Purpose:** Run the full CI gate — tests, security scans, build verification.

**Tools invoked:**
- `flutter test` / `npm test` / `pytest` / `cargo test`
- `trivy fs .` (full filesystem scan)
- `brakeman -q` (Rails — her project only)
- Build artifact verification (build/ or dist/ exists and is non-empty)

**Files created/modified:**
- `test-results.json` (parsed test output)
- `security/trivy-ci-report.json`
- `ci-report.json` (stage output)

**Scoring rubric:**
| Check | Weight | Deduction |
|-------|--------|-----------|
| Tests pass | Critical | -30 + -10 per additional failure |
| Trivy: no CRITICAL CVEs | Critical | -25 per CRITICAL |
| Brakeman: no high-severity | High | -20 per high (Rails only) |
| Build artifacts present | Medium | -10 if missing |

**Soldier expertise:** `utility` or `build-engineer` role — runs tests and collects results.

**Bypass condition:** Never bypassed on CI. Local dev: can skip with `--skip cipr`.

---

### 5.6 VERIFY Stage

**Purpose:** Composite score averaging all prior stages. Final gate before ARCHIVE.

**No tools invoked directly.** Reads scores from manifest's `stage_scores` dictionary.

**Scoring logic:**
```
composite = average of [pre_commit, build, harden, legal, cipr] scores
if any stage < 50: composite -= 10
elif any stage < 70: composite -= 5
final = max(0, round(composite))
```

**Files created/modified:**
- None (reads manifest, updates `stage_scores.verify`)

**Gating:**
- ≥70: proceed to ARCHIVE
- 50-69: warn, proceed to ARCHIVE (fix recommended but not blocking)
- <50: BLOCK — re-queue FIX soldier for failing stages

**Soldier expertise:** Not a soldier — computed by `hero score` itself (called by orchestrator).

**Bypass condition:** Never bypassed in execution line. Always runs as final composite gate.

---

### 5.7 ARCHIVE Stage

**Purpose:** Store build artifacts, SBOM, legal docs, and memory consolidation.

**Tools invoked:**
- `git worktree remove` (cleanup pipeline branch)
- Memory consolidation: journal.md → sandbox memory file
- Symbol map storage (Flutter: `build/debug-info/`)
- SBOM + legal artifacts committed to repo

**Files created/modified:**
- `memory/YYYY-MM-DD.md` (sandbox memory)
- `legal/` directory (committed to repo)
- `build/` artifacts (retained per project policy)
- Journal consolidation in sandbox memory

**Scoring rubric:**
| Check | Weight | Deduction |
|-------|--------|-----------|
| Journal consolidated | Low | -10 if missing |
| Build artifacts stored | Low | -10 if missing |
| Legal artifacts committed | Low | -10 if missing |

**Soldier expertise:** `archivist` role — inline Python journaling + synthesis.

**Bypass condition:** Never bypassed in execution line (mandatory per May 28 rules).

---

## Section 6 — Integration Checklist

### 6.1 `cli.py` Changes

**What changes:** None required at the structural level. All new pipeline stages are invoked from within `go.py`, which is already registered as a command. The `score` command is already registered.

**What to verify:**
- [ ] `go.py` import is present (already is: `from hero.commands.go import go`)
- [ ] `score.py` import is present (already is: `from hero.commands.score import score`)
- [ ] No new CLI commands needed — stages are internal to `go`

### 6.2 `config.yaml` Changes

**Additions to `~/.hero/config.yaml`:**

```yaml
# Add to existing config:
pipeline:
  execution_line:
    - pre-commit
    - build
    - harden
    - legal
    - cipr
    - verify
    - archive
  bypassable_phases:
    - council
    - research
    - prompt-engineer
    - architect
    - lead
  score_thresholds:
    pass: 70
    warn: 50
    fail: 50
  always_spawn: true
  manifest_version: "2.0"
```

**Also update:**
- `budget.default_max`: Consider increasing from 5000 → 10000 for full pipeline runs (7 stages × soldiers = more tokens)
- `spawner.timeout`: Consider increasing from 300 → 600 for stage soldiers (security scans take time)

### 6.3 `army.yaml` Changes

**New roles to add:**

```yaml
# Add to roles: section

security-scanner:
  model: "step-3.5-flash"
  provider: "stepfun-plan"
  description: "Runs security toolchain: gitleaks, semgrep, trivy, osv-scanner, socket scan. Fast tool-runner."
  context_window: 64000
  max_tokens_injected: 8000
  timeout: 300

legal-officer:
  model: "deepseek-v4-flash"
  provider: "opencode-go"
  description: "Runs license-checker, SBOM generation, EULA templating, SPDX validation. Reads legal-config.json."
  context_window: 128000
  max_tokens_injected: 12000
  timeout: 300

build-engineer:
  model: "qwen/qwen3.6-plus"
  provider: "openrouter"
  description: "Runs project build with hardening flags. Knows Flutter, Node, Python, Rust toolchains."
  context_window: 100000
  max_tokens_injected: 10000
  timeout: 600
```

**Existing roles used:**
- `archivist` — for ARCHIVE stage (already exists)
- `utility` — for CI/PR test running (already exists, round-robin pool)

### 6.4 `go.py` → `hero go` Interaction with `hero check` and `hero score`

**Interaction model:**

```
hero go --sandbox X --task Y
  │
  ├── Phase 0-2 (bypassable): Council → Research → PE → Architect → Lead
  │     └── If bypassed: skip directly to execution line
  │
  ├── Execution Line (mandatory, always spawns soldiers):
  │     │
  │     ├── PRE-COMMIT: spawn security-scanner
  │     │     └── hero score --pipeline pre-commit → record score
  │     │
  │     ├── BUILD: spawn build-engineer
  │     │     └── hero score --pipeline build → record score
  │     │
  │     ├── HARDEN: spawn security-scanner
  │     │     └── hero score --pipeline harden → record score
  │     │
  │     ├── LEGAL: spawn legal-officer
  │     │     └── hero score --pipeline legal → record score
  │     │
  │     ├── CI/PR: spawn utility (test runner)
  │     │     └── hero score --pipeline cipr → record score
  │     │
  │     ├── VERIFY: orchestrator calls hero score --pipeline all
  │     │     └── composite score → gate decision
  │     │
  │     └── ARCHIVE: spawn archivist
  │           └── hero score --pipeline archive → record score
  │
  └── Report: summary to user
```

**`hero check` vs `hero score`:**
- `hero check` = health diagnostics (budget, heartbeat, git status, build status, circuit breaker). Quick operational check. Run before `hero go`.
- `hero score` = pipeline stage evaluation. Runs specific toolchain per stage. Called by `hero go` between stages.
- They are complementary: `hero check` says "is this sandbox healthy?"; `hero score` says "did this pipeline stage pass?"

**Call sequence in `hero go`:**
```python
# Pseudocode for go.py redesign
for stage_name in EXECUTION_LINE:
    if stage_should_bypass(stage_name, task, flags):
        manifest["steps"][stage_name] = {"status": "bypassed", "score": None}
        continue
    
    # Spawn soldier for this stage
    soldier_id = enqueue(
        sandbox=sandbox,
        task=build_stage_task(stage_name, sandbox_path, config),
        role=STAGE_ROLES[stage_name],
        ...
    )
    
    # Wait for soldier (or poll)
    wait_for_soldier(soldier_id)
    
    # Score this stage
    score_result = subprocess.run(
        ["hero", "score", "--pipeline", stage_name, "--sandbox", sandbox, "--json"],
        capture_output=True, text=True
    )
    stage_score = json.loads(score_result.stdout)
    
    # Gate
    manifest["steps"][stage_name] = {
        "status": "completed",
        "score": stage_score,
        "soldier_id": soldier_id,
    }
    
    if stage_score["score"] < 50:
        # Block — re-queue fix soldier
        handle_stage_failure(stage_name, soldier_id, sandbox)
        break  # or continue depending on severity

# After all stages:
verify_score = call_hero_score_verify(manifest)
if verify_score["score"] < 50:
    raise click.ClickException(f"Pipeline blocked: VERIFY score {verify_score['score']}/100")
```

---

## Section 7 — Legal-Compliance Skill Specification

### 7.1 Location
`~/.agents/skills/legal-compliance/SKILL.md`

### 7.2 Input/Output Contract

**Input:**
- `sandbox_path: Path` — project root
- `legal_config: dict` — parsed `legal-config.json` (or auto-detected defaults)
- `stage: str` — which legal sub-stage to run (license, sbom, eula, full)

**Output:**
- `legal/LEGAL_GATE_REPORT.md` — pass/fail with evidence table
- `legal/EULA.md` — generated EULA
- `legal/PRIVACY.md` — generated Privacy Policy
- `legal/TOS.md` — generated Terms (conditional)
- `legal/SBOM.spdx` or `legal/SBOM.json` — SBOM manifest
- `legal/license-scan.json` — raw license-checker output
- Returns dict: `{"passed": bool, "score": int, "blockers": list[str], "warnings": list[str]}`

### 7.3 Trigger Conditions

The skill is invoked by `hero go` when:
1. Pipeline reaches LEGAL stage (mandatory on CI/SHIP)
2. User runs `hero legal --sandbox X` directly
3. Dependency-only change detected (fast path: license scan + SBOM diff only)
4. Nightly audit cron

### 7.4 Workflow (7 Steps)

```markdown
## Step 1: Read Config
Read sandbox_path / "legal-config.json"
If missing: generate default config based on project detection

## Step 2: License Scan
Run: npx license-checker --production --json
Parse output: compare each dependency license against ossAllowlist/ossBlocklist
BLOCK if: any blocked license found without explicit override in config

## Step 3: SBOM Generation
Run: npx @cyclonedx/cyclonedx-npm (Node) OR spdx-tools (Dart/other)
Validate: npx spdx-tools validate OR cyclonedx validate
BLOCK if: SBOM generation fails OR validation fails

## Step 4: EULA Generation
Source: ~/Development/legal-templates/Commercial-Standard-License/License.md
Substitutions: {project_name}, {year}, {jurisdiction}, {company}
Output: legal/EULA.md
BLOCK if: template missing OR substitution fails

## Step 5: Privacy Policy Generation
Tool: openterms (call via npx or programmatic API)
Config: tracking=false, retargeting=false (based on legal-config.json dataCollection)
Output: legal/PRIVACY.md
WARN if: openterms unavailable (fallback: generate minimal template)

## Step 6: Copyright Headers
Scan: all source files in project
Inject: SPDX-License-Identifier: MIT (or per-file license from SBOM)
Skip: node_modules, build, dist, .git
WARN if: injection fails for any file

## Step 7: Gate Report
Write: legal/LEGAL_GATE_REPORT.md
Format:
  ## LEGAL GATE — {timestamp}
  ### Result: PASS / FAIL
  ### Score: {score}/100
  ### Blockers:
    - {blocker 1}
    - {blocker 2}
  ### Warnings:
    - {warning 1}
  ### Evidence:
    | Check | Result | Detail |
    |-------|--------|--------|
    | License scan | pass/fail | {summary} |
    | SBOM | pass/fail | {format} |
    | EULA | pass/fail | {path} |
    | Privacy Policy | pass/fail | {path} |
    | Copyright headers | {count}/{total} | {missing count} |
```

### 7.5 Template Registry

| Template | Source Path | Substitution Variables |
|----------|-------------|----------------------|
| EULA | `~/Development/legal-templates/Commercial-Standard-License/License.md` | `{project_name}`, `{year}`, `{jurisdiction}`, `{company}` |
| Privacy Policy | openterms `appPrivacy` | `{tracking}`, `{retargeting}`, `{data_types}`, `{jurisdiction}` |
| ToS | openterms `appTerms` | `{project_name}`, `{service_type}`, `{jurisdiction}` |
| Copyright Header | Inline template | `{license_id}`, `{year}`, `{copyright_holder}` |

### 7.6 Relationship to Existing Skills

This skill follows the **spec-driven-development** pattern:
- `legal-config.json` = spec
- Artifact generation = implementation
- License scan + SPDX validation = verification

No new methodology needed. The skill is a thin orchestrator: read config → run tools → generate docs → produce gate report.

---

## Section 8 — Summary Table: What to Build First

| Order | Item | Depends On | Complexity | Parallel With |
|-------|------|------------|------------|---------------|
| 0 | `hero score` (already built) | — | DONE | — |
| 1 | `pre_commit.py` stage module | score.py | Low | legal.py |
| 2 | `legal.py` stage module | legal-templates | Low | pre_commit.py |
| 3 | `build.py` stage module | score.py | Low | — |
| 4 | `harden.py` stage module | build.py | Low | — |
| 5 | `cipr.py` stage module | build.py | Low | — |
| 6 | `verify.py` stage module | all above | Low | — |
| 7 | `archive.py` stage module | all above | Low | — |
| 8 | `go.py` redesign | all stage modules | Medium | config.yaml edits |
| 9 | `config.yaml` pipeline section | — | Low | go.py redesign |
| 10 | `army.yaml` new roles | — | Low | config.yaml |
| 11 | `legal-compliance` skill | LEGAL spec (done) | Low | — |
| 12 | End-to-end testing | all above | Medium | — |

**Total estimated effort: 8–10 developer-hours** across the full rebuild, assuming tool binaries (gitleaks, eslint, trivy, semgrep, etc.) are already installed.

---

## Section 9 — Council Sign-Off

| Analyst | Role | Verdict |
|---------|------|---------|
| **Kimi 2.6** | Analyst | Accepts all resolutions. Notes: `hero score` should remain callable standalone for ad-hoc checks. Pipeline bloat concern addressed via bypass rules. Ready. |
| **GLM 5.1** | Reasoner | Accepts all resolutions. Orchestrator-controlled scoring is correct. Standalone LEGAL phase is non-negotiable. Legal skill is the right abstraction. Ready. |
| **MiMo Pro** | Synthesis | All disagreements resolved. Build order is dependency-correct. No parallelization at architecture level (stages are sequential by design). Legal skill spec is actionable. Ready to ship. |

**Final verdict: UNANIMOUS. Proceed with numbered build phases as specified.**

---

*Report generated by HERO Council — Kimi 2.6 analyst + GLM 5.1 reasoner + MiMo Pro synthesis — 2026-05-31*  
*Input: hero score implementation, security-integration/README.md, COUNCIL_REPORT_LEGAL_PHASE.md, HERO PIPELINE.md, army.yaml, config.yaml, go.py, score.py*
