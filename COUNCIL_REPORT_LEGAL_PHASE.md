# HERO Council Report — LEGAL Phase Integration
**Date:** 2026-05-31  
**Council:** Kimi 2.6 (Analyst) + GLM 5.1 (Reasoner) + MiMo Pro (Synthesis)  
**Subject:** Integrating a LEGAL phase into the HERO pipeline for Melody_MD and all future HERO projects  
**Status:** VERDICT REACHED — recommendations below  

---

## Executive Summary

Legal exposure is already scoped as a Tier 1 attack vector in the security-integration master plan, but it has no dedicated pipeline phase. This report resolves that gap. The council agrees: **a standalone LEGAL phase is mandatory, reusable, and must fire before every production release.** For Melody_MD specifically, the phase is actionable now using the two cloned legal-templates repos.

---

## Section 1 — Convergence (Points of Full Agreement)

All three analysts agree on the following:

### 1.1 LEGAL Must Be a Standalone Phase
- It cannot be folded into HARDEN (HARDEN is hardening; LEGAL is compliance and liability)
- It cannot be deferred to Archivist (Archivist records; it does not produce legal artifacts)
- It must be **bypassable for small/solo tasks** per the existing pipeline negotiability rule — but mandatory before any SHIP

### 1.2 Position in the Pipeline
```
Council → Research → PE → Architect → Lead → Soldiers → VERIFY →
HARDEN → **LEGAL** → CI/PR → Fix (if failed) → Janitor → Archive → Archivist
```
- LEGAL sits **between HARDEN and CI/PR**
- Rationale: HARDEN finishes code-level hardening (obfuscation, root detection). LEGAL then runs compliance checks and generates legal artifacts. CI/PR then runs with legal gates active. If LEGAL fails, Fix re-queues. This keeps CI green.

### 1.3 What LEGAL Produces (minimum viable)
| Artifact | Source/Tool |
|----------|-------------|
| EULA (custom or standard) | Commercial-Standard-License repo |
| Privacy Policy (Markdown) | openterms (`appPrivacy`) |
| Terms of Service | openterms (`appTerms`) |
| SBOM (SPDX format) | spdx-tools + CycloneDX |
| License scan report | `npx license-checker --production` |
| Copyright headers (source files) | Template + SPDX identifiers |
| App Store compliance checklist | Generated checklist (Apple + Google) |

### 1.4 Legal Gate = Blocking
- Unapproved copyleft license (GPL-2.0, GPL-3.0, AGPL-3.0, SSPL) in dependencies → **CI failure**
- Missing EULA or Privacy Policy in app bundle → **CI failure**
- SBOM not generated or SPDX validation fails → **CI failure**
- Allowed licenses (MIT, Apache-2.0, BSD-2/3-clause, ISC) pass automatically

### 1.5 Reusable Across All HERO Projects
- Same LEGAL phase runs for Melody_MD, QuranAudio, fury-os, her, Freya, QLearner, sook_pro
- Project-specific config (jurisdiction, data collection flags, OSS dependencies) drives output
- Template registry pattern: each project declares `legal-config.json`; LEGAL phase reads it and generates artifacts

### 1.6 Archivist Fires Regardless
- Non-negotiable per May 28 rules
- LEGAL phase passes or fails, Archivist still records: what artifacts were generated, license scan results, any blockers

### 1.7 Melody_MD Zero-Data Special Case
- Melody_MD collects **zero user data** (all local, AES-256-GCM, no network calls, no analytics, no ads)
- openterms `appPrivacy` can be invoked with `tracking: false, retargeting: false, shop: false, gdpr: false` (simplified for offline apps)
- UAE PDPL compliance is straightforward: no PII processing = no PDPL registration needed (but explicit "no data collected" statement required in Privacy Policy)
- No GDPR consent flows needed (no data, no lawful basis required)
- No COPPA compliance burden (no data collection from children or otherwise)
- This makes Melody_MD the lowest-friction first deployment for the LEGAL phase

---

## Section 2 — Disagreements (Resolved Below)

### Disagreement A: Standalone Phase vs. Sub-Phase of SHIP

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | LEGAL should be a **sub-phase of SHIP/ARCHIVE** | "Adding a 7th mandatory phase adds ~1-2 pipeline steps for every build. Legal only matters at release time, not during development. Embedding it in SHIP keeps the pipeline lean during DEV cycles." |
| **GLM 5.1** | LEGAL should be a **standalone mandatory phase** | "Legal exposure is an attack vector with CI-blocking consequences — same as HARDEN. If LEGAL is buried in SHIP, Fix cycles become ambiguous (is it a code bug or a legal failure?). A standalone phase makes failures explicit, traceable, and fixable." |
| **MiMo Pro** | **Standalone** (resolving toward GLM) | "Kimi's concern about pipeline bloat is valid but premature — LEGAL for Melody_MD is ~30 seconds of SBOM generation + text templating, not a multi-hour process. Making it a sub-phase of SHIP would also create an ambiguous state: if LEGAL fails mid-SHIP, what does 'FIX' mean? A code fix or a legal doc fix? Standalone phase removes this ambiguity." |

**Resolution:** Standalone phase. Pipeline bloat concern noted and will be addressed via trigger conditions (see §3.4).

---

### Disagreement B: Trigger Frequency — Every Build vs. Pre-SHIP Only

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | **Pre-SHIP only** | "Running license-checker on every local build is noise. Developers don't need to see legal output on every `flutter analyze`. Legal only matters when something ships." |
| **GLM 5.1** | **Every CI run (all builds)** | "A copyleft dependency could be introduced in any PR. If LEGAL only runs pre-SHIP, a bad merge sits in `main` for days. CI should fail fast on legal exposure, same as security scanning." |
| **MiMo Pro** | **Hybrid: CI always runs; local builds skip** | "CI should always run the license scan (catches supply-chain risk). Local builds skip full LEGAL to avoid noise. Pre-SHIP triggers the full artifact generation (EULA, Privacy Policy, SBOM). This satisfies both positions: fast local dev, safe CI." |

**Resolution:** Hybrid model (MiMo synthesis):
- **Local/DEV builds:** LEGAL bypassable (skips artifact generation, runs no-op)
- **CI/PR builds:** License scan + SBOM + SPDX validation mandatory and blocking
- **Pre-SHIP builds:** Full LEGAL artifact generation (EULA, Privacy Policy, ToS, checklist) mandatory and blocking
- **Nightly periodic:** Full legal audit (re-scan all dependencies, validate all app store metadata)

---

### Disagreement C: EULA Source — Custom vs. Template

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | Use **Apple Standard EULA** for Apple builds; custom EULA only for Android + web | "Apple's Standard EULA is sufficient for most indie/small-team apps. Custom EULA requires legal review and ongoing maintenance. Why pay lawyer fees for a Flutter markdown reader?" |
| **GLM 5.1** | **Custom EULA** from Commercial-Standard-License repo | "The Commercial-Standard-License repo is specifically designed for proprietary/closed-source software and includes: governing law clause (UAE), termination, liability cap, prohibited uses including reverse engineering — exactly what a Flutter app needs for RE protection alignment. Apple Standard EULA doesn't cover UAE jurisdiction." |
| **MiMo Pro** | **Custom EULA** for flagship + re-evaluate per app | "Melody_MD and QuranAudio are flagship products where IP matters. Use the custom EULA for those. For smaller/internal tools, Apple Standard EULA is fine. Create a project-type flag in `legal-config.json` that selects the EULA source." |

**Resolution:** Custom EULA via Commercial-Standard-License for all HERO products released under HERO's name. Project config flag allows override to Apple Standard EULA for specific cases.

---

### Disagreement D: Should a Custom Skill Be Created?

| Analyst | Position | Argument |
|---------|----------|----------|
| **Kimi 2.6** | **No custom skill** — use existing `spec-driven-development` + CI scripts | "Skills are for development workflows, not legal document generation. Adding a legal skill is scope creep. Use the existing skill pattern: write a spec for the legal phase, implement via CI scripts." |
| **GLM 5.1** | **Yes — create a `legal-compliance` custom skill** | "A custom skill encodes the legal-phase workflow so it's reusable and auditable. Skills already exist for CI/CD, shipping, security. Legal fits the same pattern. Without a skill, the knowledge lives only in agent memory and is lost between sessions." |
| **MiMo Pro** | **Yes, custom skill — but lightweight** | "GLM is right on reusability. Kimi is right that this shouldn't be a heavy skill. Create `legal-compliance` as a lightweight skill (1 SKILL.md + templates) that wraps the existing `spec-driven-development` pattern for legal artifacts. The skill's job: read `legal-config.json` → generate artifacts → run scans → produce gate report. Thin wrapper, high reusability." |

**Resolution:** Create a lightweight `legal-compliance` custom skill. It follows the spec-driven-development pattern but for legal artifacts. The skill is a thin orchestrator, not a new legal analysis engine.

---

## Section 3 — Verdict (Final Recommendations)

### 3.1 Updated Pipeline Diagram

```
USER
  │
  ▼
┌────────────────────────────────────────────────────────────────┐
│  COUNCIL (bypassable)                                         │
│  Research (bypassable) → PE (bypassable) → Architect           │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  LEAD → SOLDIERS (mandatory, no solo work)                    │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  VERIFY (mandatory)                                           │
│  Build pass? Analyzer pass? Security scan?                     │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  HARDEN (mandatory — security integration)                    │
│  Obfuscation, root detection, cert pinning                     │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  ★ LEGAL (mandatory before SHIP; CI-blocking)                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ 1. License scan (license-checker)                        │ │
│  │    → FAIL if GPL/AGPL/SSPL/CPL in proprietary app        │ │
│  │ 2. SBOM generation (CycloneDX or SPDX)                   │ │
│  │ 3. SPDX validation                                       │ │
│  │ 4. EULA generation (Commercial-Standard-License)          │ │
│  │ 5. Privacy Policy (openterms appPrivacy)                  │ │
│  │ 6. Terms of Service (openterms appTerms)                  │ │
│  │ 7. Copyright headers (SPDX identifiers in source files)   │ │
│  │ 8. App Store compliance checklist (Apple + Google)        │ │
│  │ 9. LEGAL GATE report (pass/fail + evidence)               │ │
│  └──────────────────────────────────────────────────────────┘ │
│  PASS → CI/PR                                                 │
│  FAIL → FIX (re-queue soldier or amend config)                │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  CI / PR GATE                                                 │
│  Semgrep, Trivy, OSV-Scanner, Socket CLI, Brakeman            │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  FIX (mandatory if VERIFY/HARDEN/LEGAL/CI failed)             │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  JANITOR → ARCHIVE (mandatory)                                │
│  Symbol maps, SBOM, legal artifacts stored                     │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│  ARCHIVIST (mandatory throughout)                              │
│  Records all phases, all artifacts, all outcomes               │
└────────────────────────────────────────────────────────────────┘
```

**Key rule:** LEGAL gates CI/PR. If LEGAL fails, CI does not run. Fix must address the legal failure before re-triggering CI. Archivist fires regardless of LEGAL outcome.

---

### 3.2 What LEGAL Phase Produces (Detailed)

#### Melody_MD Specific Output

| Artifact | Template Source | Melody_MD Config |
|----------|----------------|-----------------|
| **EULA** | Commercial-Standard-License `License.md` | Proprietary, UAE governing law, AES encryption + RE prohibition clauses |
| **Privacy Policy** | openterms `appPrivacy` | `tracking:false, retargeting:false, shop:false, gdpr:false` — simplified "no data collected" version |
| **Terms of Service** | openterms `appTerms` | Basic terms, no account/service clause needed |
| **SBOM** | CycloneDX + SPDX | All `pubspec.yaml` dependencies |
| **License scan** | `npx license-checker --production` | Allow-list: MIT, Apache-2.0, BSD |
| **Copyright headers** | SPDX identifier template | `// SPDX-License-Identifier: MIT` in all Dart files |
| **App Store checklist** | Generated markdown | Apple EULA required, Privacy Policy URL required, zero data = simplified Data Safety form |

#### Reusable for All Projects

Each project has a `legal-config.json`:
```json
{
  "project": "melody_md",
  "type": "mobile_app",
  "jurisdiction": "UAE",
  "eulaSource": "commercial-standard-license",
  "dataCollection": "none",
  "hasAccounts": false,
  "hasBackend": false,
  "ossAllowlist": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"],
  "ossBlocklist": ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"],
  "stores": ["apple_app_store", "google_play"],
  "targetAudience": "general",
  "childDirected": false
}
```

Different `dataCollection` values trigger different Privacy Policy configurations in openterms.

---

### 3.3 Integration with Skills

**New skill: `legal-compliance` (custom, lightweight)**

Location: `~/.agents/skills/legal-compliance/SKILL.md`

```
LEGAL PHASE SKILL
=================
Input: sandbox path + legal-config.json + pipeline manifest
Output: legal-gate-report.md + generated artifacts in sandbox/legal/

Steps:
1. Read legal-config.json from sandbox root
2. Run license-checker against dependency manifests
   → Compare against ossAllowlist/ossBlocklist
   → FAIL if blocked license found without override
3. Generate SBOM (CycloneX for JS/TS, SPDX for Dart)
4. Validate SBOM (spdx-tools validate or cyclonedx validate)
5. Generate EULA:
   - commercial-standard-license → parse License.md template
   - apple-standard → use Apple's default EULA text
   - Substitute: project name, jurisdiction, year
6. Generate Privacy Policy:
   - Call openterms appPrivacy with config-derived options
   - Simplify for "dataCollection: none" case
7. Generate Terms of Service (if hasAccounts or hasBackend)
8. Inject copyright headers into source files (SPDX identifiers)
9. Generate App Store compliance checklist
10. Write LEGAL_GATE_REPORT.md (pass/fail + evidence)
11. Hand back to pipeline: PASS → CI/PR, FAIL → Fix
```

**Relationship to spec-driven-development:**  
The legal skill follows the same pattern as spec-driven-development:
- `legal-spec.md` (legal-config.json + checklist) → `legal-implementation` (generated artifacts) → `legal-verification` (license scan + SPDX validation)
- This means the existing spec-driven-development skill's workflow applies directly — no new methodology needed

---

### 3.4 Trigger Conditions

| Scenario | LEGAL Runs? | Mode |
|----------|-------------|------|
| `flutter analyze` (local dev) | ❌ No | Bypassed — too noisy |
| `flutter test` | ❌ No | Bypassed |
| Local `flutter build` (pre-SHIP check) | ✅ Yes | Full artifact generation |
| CI on PR | ✅ Yes | License scan + SBOM only (fast) |
| CI on merge to main | ✅ Yes | Full artifact generation |
| `hero go --ship` | ✅ Yes | Full phase, mandatory |
| Version bump only (no code change) | ✅ Yes | SBOM only (fast path) |
| First release of new project | ✅ Yes | Full + extra: copyright registration reminder |
| Periodic (nightly) | ✅ Yes | Full re-audit of all HERO repos |

**Fast path for dependency-only changes:** Skip EULA/Privacy Policy regeneration (they haven't changed), run only license scan + SBOM diff.

---

### 3.5 Toolchain Recommendations for Melody_MD

#### Primary Tools (Use Now)

| Tool | Purpose | Command |
|------|---------|---------|
| **Commercial-Standard-License** (cloned repo) | EULA template | `cp ~/Development/legal-templates/Commercial-Standard-License/License.md sandbox/legal/EULA.md` + string substitution |
| **openterms** (cloned repo, install as dep) | Privacy Policy + ToS generation | `npx @entva/openterms appPrivacy 'en' { config }` or programmatic call |
| **license-checker** (npm, global) | Dependency license scan | `npx license-checker --production --json > sandbox/legal/license-scan.json` |
| **CycloneDX** (npm) | SBOM generation | `npx @cyclonedx/cyclonedx-npm --output-file sandbox/legal/sbom.json` |
| **spdx-tools** (npm) | SPDX validation | `npx spdx-tools validate sandbox/legal/sbom.spdx` |

#### Supplementary (Add in CI Pipeline)

| Tool | Purpose | When |
|------|---------|------|
| **FOSSA CLI** | Advanced OSS compliance (free tier) | CI, post-dependency install |
| **scancode-toolkit** | Deep license + copyright detection | CI, nightly |
| **ORT** (OSS Review Toolkit) | Enterprise-grade compliance | P2, when scaling to multiple flagship products |

#### Not Needed for Melody_MD (Document Why)

| Tool | Reason Skipped |
|------|---------------|
| **Copyright registration** | P0 only for revenue-generating flagship; Melody_MD is pre-revenue, defer to first revenue milestone (~$65 one-time cost) |
| **DMCA agent registration** | Defer until first infringement incident; register DMCA agent with US Copyright Office (~$160) |
| **GDPR consent management** | Melody_MD collects zero data; GDPR consent flows unnecessary |
| **CCPA "Do Not Sell" link** | No data sale; one-line statement in Privacy Policy sufficient |
| **WCAG automated scan** | Flutter apps: use `flutter_test` + `semantics` testing; add `axe-core` equivalent when web version ships |

---

## Section 4 — Recommended Next Actions

### Immediate (This Session)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 1 | **Create `legal-compliance` skill** | Council → Implementer | `~/.agents/skills/legal-compliance/SKILL.md` + templates directory |
| 2 | **Create Melody_MD `legal-config.json`** | Lead | Based on §3.2 config, place at `~/Development/Melody_MD/legal-config.json` |
| 3 | **Add LEGAL phase to pipeline manifest schema** | Architect | Update `~/.hero/pipeline/*.json` schema to include `legal` phase |
| 4 | **Run first LEGAL phase on Melody_MD** | Council → Lead dispatch | Spawn soldier to run full LEGAL phase on Melody_MD as proof-of-concept |

### Short-Term (Next Sprint)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 5 | **Install openterms as devDependency** | Lead | `npm install --save-dev @entva/openterms` in Melody_MD (or call via npx) |
| 6 | **Add LEGAL gate to CI** | CI/CD engineer | GitHub Actions: license-checker + SBOM generation + SPDX validation as blocking check |
| 7 | **Create EULA acceptance flow in Melody_MD** | Soldier | First-launch dialog showing EULA; acceptance stored in shared preferences |
| 8 | **Add `NOTICE.md` / `THIRD-PARTY-LICENSES.md`** | Soldier | Auto-generated from license-checker output, bundled in app assets |
| 9 | **Legal config for all HERO projects** | Council | Create `legal-config.json` for fury-os, her, Freya, QLearner, sook_pro |

### Medium-Term (Next Month)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 10 | **Copyright registration for Melody_MD** | Council → User | US Copyright Office, first 25 + last 25 pages with trade secret redactions (~$65) |
| 11 | **DMCA agent registration** | User | Register with US Copyright Office (~$160 one-time) |
| 12 | **Scale legal-compliance skill to all projects** | Council | Each project gets own legal-config.json; skill reads it generically |
| 13 | **Nightly legal audit for all HERO repos** | CI/CD | Automated nightly run of full LEGAL phase across all active projects |
| 14 | **App Store submission with LEGAL artifacts** | Lead → User | EULA, Privacy Policy URL, Data Safety form, SBOM committed to release |

### Backlog (P2)

| # | Action | Owner | Details |
|---|--------|-------|---------|
| 15 | **FOSSA CLI integration** | CI/CD | Free tier for advanced OSS compliance scanning |
| 16 | **scancode-toolkit for deep license detection** | CI/CD | Detect license text in binary/compiled assets |
| 17 | **Legal review gate (human-in-loop)** | User | Before first production release, have qualified counsel review EULA + Privacy Policy |
| 18 | **Accessibility scan integration** | Council | axe-core or pa11y in CI for web; Flutter semantics tester for mobile |

---

## Section 5 — Council Sign-Off

| Analyst | Role | Verdict |
|---------|------|---------|
| **Kimi 2.6** | Analyst | Accepts resolution on A and B; notes pipeline bloat concern will be addressed via trigger conditions. Stands by Apple Standard EULA for non-flagship products. |
| **GLM 5.1** | Reasoner | Accepts resolution on C and D; custom EULA + custom skill are correct for long-term maintainability. Hybrid trigger model is pragmatically sound. |
| **MiMo Pro** | Synthesis | All three disagreements resolved. Verdict: standalone LEGAL phase, hybrid trigger, custom EULA for flagships, custom lightweight skill. Ready to ship. |

**Final verdict: UNANIMOUS with noted reservations (Kimi on EULA source for non-flagship products).**

---

## Appendix A — Melody_MD Legal Quick-Start

The fastest path to a shippable Melody_MD with legal protection:

```
1. Create legal-config.json  ← 2 minutes
2. Install license-checker + CycloneDX  ← npm install
3. Run: npx license-checker --production  ← check for GPL in pubspec.lock
4. Run: npx @cyclonedx/cyclonedx-npm  ← generate SBOM
5. Copy Commercial-Standard-License/License.md → EULA.md, substitute Melody_MD
6. Call openterms appPrivacy → Privacy Policy (no-data variant)
7. Add EULA acceptance screen (1 Flutter widget, ~30 min implementation)
8. Add Privacy Policy link in app Settings screen
9. Commit legal/ directory to repo
10. Submit to App Store with EULA + Privacy Policy URL
```

**Total time estimate:** 2-3 hours for full LEGAL phase execution on Melody_MD (first run). Subsequent releases: ~15 minutes (regenerate EULA/PP if config changed; otherwise SBOM + license scan only).

---

## Appendix B — Legal Disclaimer

> **This document is a council report and operational plan. It does not constitute legal advice.**  
> The HERO Council is an AI analysis system, not a law firm.  
> **Before shipping Melody_MD or any HERO product to production, consult qualified legal counsel** to review:  
> - Custom EULA for UAE jurisdiction enforceability  
> - Privacy Policy accuracy for "no data collection" claim  
> - App Store submission compliance with Apple/Google current terms  
> - Copyright registration strategy for flagship products  

The plan is sound, the tools are real, but legal questions require human legal expertise.

---

*Report generated by HERO Council — Kimi 2.6 analyst + GLM 5.1 reasoner + MiMo Pro synthesis — 2026-05-31*  
*Input: security-integration/README.md, legal-templates repos, HERO docs/PIPELINE.md, legal-protection-research.md*
