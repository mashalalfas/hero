# HERO Teach Skill — Website Design

> **Version:** 1.0.0
> **Date:** 2026-06-07
> **Status:** Design — ready for build
> **Audience:** HERO maintainers, contributors, and curious newcomers
> **Owners:** HERO docs team

---

---

> **UI/UX Refinement:** This design has been reviewed through the UI-UX-Pro-Max design intelligence skill (161 color palettes, 57 font pairings, 161 product types, 99 UX guidelines, 25 chart types). Key refinements from the skill are marked with 🎨 throughout.

---

## 1. Vision

### What the Teach Skill is

The **Teach Skill** is a marketing + educational website that introduces HERO to the world. It is not a substitute for `SPEC.md`, `README.md`, or the in-repo `docs/` — those remain the source of truth for contributors. The Teach Skill is the **front door**: a place where a developer lands, understands what HERO does in 30 seconds, sees the pipeline animated, explores the architecture, and walks away ready to `pip install` it.

It is called a "skill" because it is built and consumed the same way HERO consumes other skills (research, archival, etc.) — declaratively, from a `.md` plan, with a clear input contract and a measurable output. Concretely, the site is a static artefact that:

1. **Teaches** the HERO mental model — multi-agent orchestration, the pipeline, TOON, sandboxes.
2. **Demonstrates** the pipeline as an interactive animation rather than a wall of text.
3. **References** the rest of the HERO docs through deep links, never duplicating them.
4. **Onboards** new operators with copy-paste commands that go from `pip install` to first `hero go`.

### Why it exists

| Without the Teach Skill | With the Teach Skill |
|---|---|
| Newcomers hit `SPEC.md` and bounce. | Land on a one-page story: "this is HERO, this is what it does, this is how to try it." |
| The pipeline is described in 4 different ASCII diagrams across 4 docs. | One canonical, animated pipeline map drives every explanation. |
| The 30+ commands are a flat table in `README.md`. | A searchable command reference with examples, grouped by lifecycle. |
| "Why does this exist?" is answered in a 200-line intro. | A 30-second pitch above the fold, with depth available on scroll. |
| `EXCHANGE_LAYER_SPEC.md` is invisible unless you go hunting. | A dedicated "Architecture" page surfaces it as a first-class concept. |

### 🎨 Delivery model: `hero teach` CLI command

This site is not a standalone marketing URL — it's launched via:

```bash
hero teach              # Opens the site in default browser
hero teach --page pipeline   # Deep-link to a specific page
hero teach --server-only     # Start dev server without opening browser
hero teach --offline         # Open local bundle (no network, no live data)
```

The site is a **local static-first website** shipped with HERO:
- Static build lives at `~/.hero/teach/` (installed during `pip install`)
- `hero teach` does: start a tiny local HTTP server → open browser → auto-close on idle
- No external hosting dependency. Works offline. No analytics.
- Updates come with `pip install --upgrade hero` (the site is a build artefact)

This ship method matches how developer tools teach themselves: `man hero`, `hero --help`, `tldr hero`, `hero docs`.
The 

1. **Show, don't tell.** Every concept gets a visual: a node in a graph, a coloured stage badge, an animated message flowing between sandboxes.
2. **One canonical pipeline map.** The same SVG/Canvas component renders everywhere — landing page, architecture page, command reference, getting-started page. The only thing that changes is the level of detail.
3. **TOON-first examples.** Code samples use TOON, not JSON, to teach the format implicitly. The "before/after" token count is a teaching moment.
4. **Static where possible.** No backend, no auth, no database. The site is a static build with a tiny client-side script for interactivity.
5. **Dark mode is the default.** HERO is a developer tool used in terminals. Most users will have dark themes. We honour `prefers-color-scheme` and ship a toggle.
6. **Mobile-friendly but desktop-first.** The pipeline map shines on a wide screen. On mobile it stacks vertically but stays fully navigable.

### Audience and tone

| Audience | What they need | Tone |
|---|---|---|
| Curious developer (LinkedIn/Twitter) | "What is this in one paragraph?" | Punchy, confident, technical but not jargon-heavy |
| Evaluating engineer (GitHub README click) | "Is this real, is it maintained, can I run it?" | Evidence-driven, code samples, no marketing fluff |
| New operator (first install) | "Show me the commands, in order" | Calm, step-by-step, with expected output |
| Contributor (deep dive) | "Where do I start in the codebase?" | Direct links to `SPEC.md`, `PIPELINE.md`, `EXCHANGE_LAYER_SPEC.md` |
| Architect peer (industry) | "How is the exchange layer different from Agent Teams?" | Comparison tables, design rationale |

The voice is **engineering-first**: assume the reader is technical, never condescend, never over-explain, and never apologise for the project's scope.

---

## 2. Site Architecture

### Top-level pages

```
/                     Landing         — what is HERO, who is it for, the pitch
/architecture         Architecture    — interactive pipeline map + system diagram
/pipeline             Pipeline        — deep-dive on the 7-stage pipeline
/exchange             Exchange Layer  — inter-agent messaging (linked from spec)
/commands             Commands        — searchable reference of all hero commands
/roles                Roles           — what each agent role does
/getting-started      Getting Started — install, scan, spawn, go
/examples             Examples        — annotated real-world runs
/learn                Learn           — curated reading path through the docs
/about                About           — vision, history, contributing
```

### Information architecture (navigation)

```
HERO
├── Get Started
│   ├── Install
│   ├── First Scan
│   ├── First Spawn
│   └── First Go
├── Concepts
│   ├── Sandbox
│   ├── Soldier
│   ├── TOON Format
│   ├── Pipeline
│   ├── Exchange Layer
│   └── Reliability (DLQ, Circuit Breaker, Budgets)
├── Reference
│   ├── Commands (A–Z)
│   ├── Roles
│   ├── State Files
│   └── Config
├── Examples
│   ├── Bug fix in Flutter app
│   ├── Refactor across 3 sandboxes
│   └── Adversarial review with exchange
└── About
    ├── Why HERO
    ├── Roadmap
    └── Contributing
```

### Content hierarchy per page

Every page follows a **3-tier depth pattern**:

1. **Tier 1 — 30-second pitch** (above the fold, no scroll)
   - One sentence: what this page is about
   - One diagram: the relevant visual
   - One CTA: next link

2. **Tier 2 — Working knowledge** (one scroll)
   - The 3–5 things you need to *use* this
   - Code samples that actually run
   - A "common mistakes" callout

3. **Tier 3 — Deep dive** (further reading)
   - Links to canonical docs (`SPEC.md`, `PIPELINE.md`, etc.)
   - Design rationale
   - Trade-offs and alternatives considered

This pattern recurs on every page so users build a mental model of the site's structure.

### URL strategy

- **Trailing slash on:** root, concepts, examples, about.
- **No trailing slash on:** specific command pages (`/commands/go`), role pages (`/roles/soldier`).
- **Stable anchors:** `#pipeline`, `#sandbox`, `#toon`, `#exchange`, `#reliability` — so docs and blog posts can deep-link.

### File routing (Vite + React Router — see §5)

```
src/
  pages/
    Home.tsx
    Architecture.tsx
    Pipeline.tsx
    ExchangeLayer.tsx
    Commands.tsx
    CommandPage.tsx
    Roles.tsx
    RolePage.tsx
    GettingStarted.tsx
    Examples.tsx
    ExamplePage.tsx
    Learn.tsx
    About.tsx
    NotFound.tsx
```

---

## 3. Pipeline Map Design

The **Interactive Pipeline Map** is the centrepiece of the site. It appears in three places at three different levels of detail:

1. **Landing page** — overview, animated, no interactions
2. **Architecture page** — full diagram, click-to-explode, all components
3. **Pipeline page** — stage-by-stage drill-down, with code and score explanations

### 3.1 Layout

The pipeline has two halves: the **planning/orchestration** half (left/top) and the **execution** half (right/bottom).

```
Planning & Orchestration                    Execution & Verification
─────────────────────────                   ─────────────────────────

┌─────────┐                                 ┌──────────┐
│ Council │──┐                              │ PRE-     │ score 0-100
└─────────┘  │                              │ COMMIT   │ ≥70 pass / <50 fail
             ▼                              └────┬─────┘
┌─────────┐  ┌──────────┐  ┌──────────┐         ▼
│Research │─►│  Prompt  │─►│Architect │   ┌──────────┐
│         │  │Engineer  │  │          │   │  BUILD   │
└─────────┘  └──────────┘  └────┬─────┘   └────┬─────┘
                                ▼              ▼
                          ┌──────────┐   ┌──────────┐
                          │   Lead   │──►│  HARDEN  │
                          │(orchestr)│   └────┬─────┘
                          └────┬─────┘        ▼
                               │         ┌──────────┐
                               │         │  LEGAL   │
                               │         └────┬─────┘
                               │              ▼
                               │         ┌──────────┐
                               │         │  CI/PR   │
                               │         └────┬─────┘
                               │              ▼
                               │         ┌──────────┐
                               │         │  VERIFY  │ ── composite gate
                               │         └────┬─────┘
                               │              ▼
                               │         ┌──────────┐
                               │         │ ARCHIVE  │
                               │         └──────────┘
                               │
                               ▼
                          Soldiers (parallel)
                          ┌────┐┌────┐┌────┐
                          │ S1 ││ S2 ││ S3 │
                          └─┬──┘└─┬──┘└─┬──┘
                            └─────┴─────┘
                                 │
                                 ▼
                          git commit
```

On wide screens: left-to-right. On mobile (<768px): top-to-bottom, with planning stacked above execution.

### 3.2 Visual treatment per node

Every node is a **pill** with a coloured status badge and a label. The shape is identical across all surfaces — only the colour and animation state change.

```
┌──────────────────────────┐
│ PRE-COMMIT          [92]  │  ← score (right-aligned, colour-coded)
│ ────────────────────────  │  ← thin progress bar (proportional to score)
│  secrets · lint · copy    │  ← one-line description (Tier 2 only)
└──────────────────────────┘
```

**States and colours:**

| State | Border | Background | Score badge | Animation |
|---|---|---|---|---|
| `idle` | 1px slate-700 | slate-900 | grey | none |
| `running` | 1.5px cyan-400 | slate-900 + glow | cyan-400 | pulse 1.2s |
| `passed` | 1px emerald-500 | slate-900 | emerald-400 | brief flash + checkmark |
| `warn` | 1px amber-500 | slate-900 | amber-400 | subtle shake |
| `failed` | 1px rose-500 | slate-900 | rose-400 | shake + DLQ icon |
| `quarantined` | 1px rose-700 dashed | slate-900 | rose-700 | — |

### 3.3 Edges and flow

Edges are **directed** (arrows), **animated** when active, and **labelled** with the protocol (TOON, .toon file, .json manifest, etc.) when in Tier 2/3.

```
Council ─── "toon" ───► Research
  (animated cyan dashes flow from Council to Research)
```

Animation: a 6-px dashed line, 1.2s linear loop, opacity 0.6 → 1.0 → 0.6. When the destination is `running`, the dashes speed up to 0.8s.

### 3.4 Interactivity (Architecture page)

- **Hover** a node → tooltip with name, role, expected duration, typical token budget.
- **Click** a node → side panel slides in from the right with:
  - **What it does** — 2–3 sentences, plain language
  - **Who runs it** — the role(s) and the model(s) from `army.yaml`
  - **Score meaning** — how the 0–100 number is computed
  - **Example output** — a real terminal snippet from a known run
  - **Source link** — jump to the corresponding `src/hero/commands/<stage>.py` and `docs/` file
- **Drag** to pan; **scroll** to zoom (within 50–150 %).
- **"Replay"** button top-right → re-runs the full animation from `idle` to `archive` over 12 seconds.
- **"Live"** mode (opt-in) → polls a future `hero map --format json` endpoint (currently `hero map` exists; expose JSON output as a follow-up). For v1 we ship with a recorded example.

### 3.5 Interactivity (Pipeline page)

Same component, scoped to the execution half (PRE-COMMIT → ARCHIVE). Clicking a stage reveals:

1. **What it does** — semantic, not a one-liner
2. **Who runs it** — `commands/<stage>.py`, plus which role model
3. **Score formula** — e.g. for `HARDEN`: `100 − (5 × critical_cves) − (10 × missing_root_detection) − (15 × missing_cert_pinning)`
4. **Gate** — `≥70` pass, `50–69` warn, `<50` fail
5. **Example output** — a real `hero <stage> --sandbox X` snippet with pass/warn/fail emoji
6. **Failure handling** — what happens on a fail (DLQ, retry, escalate)

### 3.6 Tech for the diagram

**Chosen:** **React Flow** (`reactflow` v11), wrapped in a `<PipelineMap>` component.

Why React Flow:
- First-class React API (matches the chosen framework in §5).
- Built-in pan, zoom, minimap, controls.
- Custom node types let us reuse the same pill across all surfaces.
- Edge animations are trivial with `animated: true` and custom edge components.
- Free, MIT, mature, and battle-tested (used by Stripe, Linear, etc.).
- Bundle size is ~80 KB gzipped — acceptable for a docs site.

Alternatives considered:
- **D3** — too low-level; we'd re-implement pan/zoom.
- **Mermaid** — not interactive enough, weak on custom styling.
- **Excalidraw** — hand-drawn aesthetic doesn't match the "engineering tool" vibe.
- **Cytoscape** — great for graphs but heavier; overkill for a linear pipeline.

### 3.7 Stages and details (canonical data)

| Stage | Role | Model | Score 0-100 | Gate | What it does |
|---|---|---|---|---|---|
| **Council** | council | custom-api-canopywave-io/moonshotai/kimi-k2.6 + glm-5.1 + mimo-v2.5-pro | n/a | quorum ≥3 | Multi-model deliberation for complex problems |
| **Research** | researcher | deepseek-v4-flash | n/a | n/a | Web/code research via DeepSeek |
| **Prompt Engineer** | prompt_engineer | MiniMax-M3 | n/a | n/a | Crafts/refines all prompt templates |
| **Architect** | architect | custom-api-canopywave-io/moonshotai/kimi-k2.6 | n/a | n/a | Architectural blueprint, file structure, risk analysis |
| **Lead** | lead | mimo-v2.5 (1M ctx) | n/a | n/a | Orchestrates the army, breaks tasks into subtasks |
| **Soldiers** | soldier | Kimi K2.6 (always) + step-3.7-flash + deepseek-v4-pro | n/a | n/a | Parallel execution — Kimi elite default |
| **PRE-COMMIT** | soldier | Kimi K2.6 / step-3.7-flash / deepseek-v4-pro | computed | ≥70 pass | Secrets scan, lint, copyright headers |
| **BUILD** | soldier | Kimi K2.6 / step-3.7-flash / deepseek-v4-pro | computed | ≥70 pass | Compile, obfuscation, ProGuard/R8, debug symbols |
| **HARDEN** | soldier | Kimi K2.6 / step-3.7-flash / deepseek-v4-pro | computed | ≥70 pass | Trivy CVE scan, secrets in build/, root detection, cert pinning |
| **LEGAL** | soldier | Kimi K2.6 / step-3.7-flash / deepseek-v4-pro | computed | ≥70 pass | License allowlist, SBOM, EULA, Privacy Policy, copyright |
| **CI/PR** | soldier | Kimi K2.6 / step-3.7-flash / deepseek-v4-pro | computed | ≥70 pass | Tests, Trivy, build artifact check, Brakeman |
| **VERIFY** | verifier | step-3.5-flash | composite | ≥70 pass | Averages all stage scores, applies penalties |
| **ARCHIVE** | archivist | step-3.5-flash | n/a | n/a | Daily memory, project section in MEMORY.md, journal entry |

Penalty rules (for VERIFY):
- −10 if any stage < 50
- −5 if any stage < 70
- Final score: `composite_avg − penalties`

### 3.8 Example run (used in animations and screenshots)

A single canonical example, **"Fix theme switcher lag in sook-pro"**, runs through the site in screenshots and animations:

```bash
hero go --sandbox sook-pro --task "Fix theme switcher lag" --auto
```

Stages animate in order. Real terminal output is captured as an SVG/PNG and embedded.

---

## 4. Content Plan

### 4.1 Landing page (`/`)

**Goal:** Convert a curious reader into a "show me the code" reader in 60 seconds.

**Above the fold (Tier 1):**
- **Headline:** "HERO — a CLI that runs an army of AI agents across your projects."
- **Subhead:** "Plan. Dispatch. Verify. Archive. One command, no babysitting."
- **Hero visual:** the pipeline map, looping animation, auto-replay every 12s.
- **Two CTAs:** `Get Started` (→ /getting-started) and `See the Pipeline` (→ /pipeline).
- **No nav clutter** — just logo, theme toggle, and "GitHub ↗" link.

**Tier 2 (one scroll):**
- **3-column "What it does":**
  1. **Discover** — `hero scan` finds every project under `~/Development/`.
  2. **Orchestrate** — Lead plans the work, soldiers execute in parallel sandboxes.
  3. **Verify** — A 7-stage pipeline scores every change; DLQ catches failures.
- **TOON vs JSON** side-by-side snippet (the "before/after" teaching moment).
- **One big code block** — the canonical "fix a bug" command from start to finish.

**Tier 3:**
- Testimonials / case studies (placeholder for v2).
- "Trusted by" / "Built on" badges (placeholder).
- Footer with deep links to all sections.

### 4.2 Architecture page (`/architecture`)

**Goal:** Show the full system in one diagram, with click-to-explore on every node.

**Sections:**
1. **System diagram** — the full pipeline map in interactive mode.
2. **Sidebar legend** — coloured badges for every role and stage.
3. **Click a node** → side panel with what/who/score/example.
4. **Bottom rail** — three small diagrams:
   - **Sandbox isolation** — each sandbox = one project dir under `~/.hero/sandboxes/`.
   - **Exchange Layer** — file-based message bus between soldiers.
   - **Reliability stack** — DLQ + Circuit Breaker + Budget tracking.
5. **Source map** — clickable tree of `src/hero/` modules, links to the actual files on GitHub.

### 4.3 Pipeline page (`/pipeline`)

**Goal:** Deep-dive on the 7-stage execution pipeline (PRE-COMMIT → ARCHIVE).

**Sections:**
1. **Overview** — the execution half of the pipeline map, scrollable.
2. **Per-stage sections** — one section per stage, in order:
   - **PRE-COMMIT** — secrets/lint/copyright; score formula; example.
   - **BUILD** — compile/obfuscate/ProGuard; example.
   - **HARDEN** — Trivy/secrets/root-detection/cert-pinning; example.
   - **LEGAL** — license/SBOM/EULA/Privacy; example.
   - **CI/PR** — tests/Trivy/Brakeman/build-artifact; example.
   - **VERIFY** — composite gate; penalty rules; example.
   - **ARCHIVE** — journal + memory; append-only invariant; example.
3. **Failure modes** — what happens on warn/fail/quarantine.
4. **Score reference table** — full grid of stage × check × weight.

### 4.4 Exchange Layer page (`/exchange`)

**Goal:** Surface the `EXCHANGE_LAYER_SPEC.md` as a first-class concept.

**Sections:**
1. **The problem** — soldiers are isolated; no coordination.
2. **The solution** — file-based message bus (`.toon` files in `~/.hero/exchange/`).
3. **5 patterns** with diagrams:
   - Direct messaging
   - Broadcast
   - Shared task list (Agent Teams pattern)
   - Result passing
   - Adversarial review
4. **CLI quick reference** — `hero exchange send/listen/broadcast/status/claim/complete/purge`.
5. **Code sample** — `from hero.exchange import ExchangeLayer`.
6. **Comparison table** — HERO vs Claude Code Agent Teams vs Gas Town.
7. **Source link** — `src/hero/exchange/` tree, link to `EXCHANGE_LAYER_SPEC.md`.

### 4.5 Commands page (`/commands`)

**Goal:** Searchable reference of all 30+ `hero` commands.

**Sections:**
1. **Search bar** — fuzzy search across command name and description.
2. **Grouped list** by lifecycle:
   - **Discovery** — `scan`, `map`, `graph`
   - **Spawn & Deploy** — `spawn`, `deploy`, `tell`, `orchestrate`, `assemble`, `go`
   - **Pipeline** — `pre-commit`, `build`, `harden`, `legal`, `cipr`, `verify`, `archive`, `score`, `pipeline`, `ready`, `sweep`
   - **State** — `status`, `budget`, `katana`, `heartbeat`, `dispatch`, `exchange`
   - **Reliability** — `dlq`, `circuit-breaker`
   - **Diagnostics** — `check`, `viewport`, `watch`, `brainstorm`, `eval`
   - **Maintenance** — `kill`, `kill-sandbox`, `clean`, `prune`
3. **Per-command card:**
   - Name and short description.
   - Synopsis (from the Click help string).
   - Example with real output.
   - Link to source file in `src/hero/commands/`.

**Data source:** Generated at build time by parsing `src/hero/cli.py` and the `click` decorators in each command module. A small Node script (`scripts/extract-commands.mjs`) walks the AST and emits `src/data/commands.json`.

### 4.6 Roles page (`/roles`)

**Goal:** Explain each agent role, what it does, which model it uses, and when it triggers.

**Sections:**
1. **Roles overview** — grid of cards: Communicator, Lead, Architect, Soldier, Researcher, Archivist, Janitor, Utility, Council, Prompt Engineer.
2. **Per-role page** (`/roles/<role>`):
   - **Purpose** — one paragraph.
   - **Model(s)** — pulled from `~/.hero/army.yaml`.
   - **Context window + max injected tokens.**
   - **Typical tasks** — example briefs.
   - **Triggers** — when does it run? (council trigger list, prompt engineer trigger list, etc.)
   - **Anti-patterns** — what it should never do.
3. **Escalation tiers** — Tier 1 → Tier 2 → Tier 3, with model mappings.

### 4.7 Getting Started page (`/getting-started`)

**Goal:** Take a new operator from `git clone` to first `hero go` in 5 minutes.

**Sections:**
1. **Prerequisites** — Python 3.11, Node (for TOON CLI), Hermes, Graphify.
2. **Install** — `./scripts/install-hero.sh` with expected output.
3. **Scan your projects** — `hero scan` with expected output.
4. **Check status** — `hero status` with expected output.
5. **Spawn your first soldier** — `hero spawn --sandbox <name> --task "..."` with expected output.
6. **Run a full pipeline** — `hero go --sandbox <name> --task "..."` with expected output.
7. **Watch it live** — `hero viewport` (screenshot of the TUI).
8. **Inspect a failure** — `hero dlq list`, `hero check --sandbox X`, `hero budget summary`.
9. **Next steps** — links to `/pipeline`, `/architecture`, `/exchange`.

### 4.8 Examples page (`/examples`)

**Goal:** Real, annotated runs of HERO solving real problems.

**Sections:**
1. **Bug fix in a Flutter app** — `hero go --sandbox sook-pro --task "fix theme switcher lag"`.
2. **Cross-sandbox refactor** — `hero deploy --targets A,B,C --task "rename User → Account"`.
3. **Adversarial review with exchange** — `hero deploy --targets builder,reviewer --exchange`.
4. **CI gate failure** — `hero cipr` returns `<50`, soldier lands in DLQ, manual retry.
5. **Council deliberation** — complex task triggers the 3-model council, output diff vs single-model.

Each example is a self-contained page with the actual command, the actual output (collapsed by default), and a written walkthrough.

### 4.9 Learn page (`/learn`)

**Goal:** Curated reading path through the docs.

**Sections:**
1. **5-minute tour** — landing + architecture pages.
2. **30-minute deep dive** — landing + architecture + pipeline + exchange.
3. **Half-day mastery** — all of the above + commands + roles + examples.
4. **Contributor track** — `SPEC.md` → `EXCHANGE_LAYER_SPEC.md` → `PIPELINE.md` → `src/hero/`.
5. **External links** — TOON format spec, Graphify docs, Hermes docs.

### 4.10 About page (`/about`)

**Goal:** Project history, vision, contributing.

**Sections:**
1. **Why HERO exists** — short essay.
2. **Roadmap** — copy from `SPEC.md` Phase 4 (Future Work).
3. **Maintainers** — placeholder.
4. **Contributing** — link to `AGENTS.md` and `BOOTSTRAP.md` (or whatever the project uses).
5. **License** — placeholder.

---

## 5. Tech Stack

### 5.1 Build & framework

| Concern | Choice | Why |
|---|---|---|
| **Framework** | **React 18 + TypeScript** | Mature, large ecosystem, excellent MDX support |
| **Build tool** | **Vite 5** | Fast HMR, simple config, great DX |
| **Router** | **React Router 6** | Standard, supports file-based or programmatic routing |
| **Content** | **MDX 3** | Author pages in markdown with React components inline |
| **Styling** | **Tailwind CSS 3** | Utility-first, fast iteration, dark mode built-in |
| **Diagram** | **React Flow 11** | See §3.6 |
| **Code highlight** | **Shiki** | VSCode-grade syntax highlighting; renders at build time (no client JS) |
| **Search** | **Fuse.js** | Tiny (~6KB), client-side fuzzy search for commands |
| **Theme** | `next-themes`-style hook (custom) | Light/dark, system preference, persisted in `localStorage` |
| **Deployment** | **Cloudflare Pages** | Free, fast, global CDN, GitHub integration, supports custom domains |
| **Analytics** | **Plausible** (self-hosted) or **none** | Privacy-friendly; if the user wants zero analytics, skip |
| **SEO** | **react-helmet-async** | Per-page `<title>`, `<meta>`, OpenGraph |

### 5.2 Static vs SPA

**Static-first, with client-side interactivity where it earns its place.**

- All pages are **pre-rendered** at build time using Vite's static-site mode.
- The pipeline map, command search, and theme toggle are **client-side** React components.
- No server. No API calls. The site is a folder of HTML/CSS/JS you can `wget -r` if you want.

This keeps hosting trivially cheap (Cloudflare Pages free tier handles ~unlimited requests for a docs site) and the site fast on any device.

### 5.3 Why this stack over alternatives

| Alternative | Verdict | Reason |
|---|---|---|
| **Astro** | Strong runner-up | Could win on bundle size; we chose Vite for React Flow's React-first API |
| **Next.js** | Rejected | SSR is overkill; we don't need a server. Adds complexity and cost. |
| **Docusaurus** | Rejected | Great for pure docs, but we need a custom React Flow integration. Docusaurus fights custom interactivity. |
| **Plain HTML** | Rejected | Command reference alone has 30+ entries; search needs JS. |
| **Hugo / Eleventy** | Rejected | Templating gets awkward with interactive components. |

### 5.4 Folder structure

```
hero-teach/
├── public/
│   ├── favicon.svg
│   └── og-default.png
├── scripts/
│   ├── extract-commands.mjs    # AST-walks src/hero/commands/, emits commands.json
│   └── extract-roles.mjs       # parses ~/.hero/army.yaml, emits roles.json
├── src/
│   ├── main.tsx
│   ├── App.tsx                 # router + layout
│   ├── components/
│   │   ├── Nav.tsx
│   │   ├── Footer.tsx
│   │   ├── ThemeToggle.tsx
│   │   ├── PipelineMap.tsx     # the centerpiece
│   │   ├── NodePill.tsx
│   │   ├── NodePanel.tsx       # side panel on click
│   │   ├── CodeBlock.tsx       # Shiki wrapper
│   │   ├── ToonVsJson.tsx      # side-by-side teaching widget
│   │   ├── ScoreBadge.tsx
│   │   └── SearchBar.tsx
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── Architecture.tsx
│   │   ├── Pipeline.tsx
│   │   ├── ExchangeLayer.tsx
│   │   ├── Commands.tsx
│   │   ├── CommandPage.tsx
│   │   ├── Roles.tsx
│   │   ├── RolePage.tsx
│   │   ├── GettingStarted.tsx
│   │   ├── Examples.tsx
│   │   ├── ExamplePage.tsx
│   │   ├── Learn.tsx
│   │   ├── About.tsx
│   │   └── NotFound.tsx
│   ├── data/
│   │   ├── commands.json       # generated
│   │   ├── roles.json          # generated
│   │   ├── pipeline.json       # hand-authored: nodes, edges, descriptions
│   │   └── examples/           # one .mdx per example
│   ├── styles/
│   │   └── globals.css
│   └── lib/
│       ├── shiki.ts            # Shiki setup
│       └── mdx.ts              # MDX components mapping
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
└── README.md
```

### 5.5 Build commands

```bash
pnpm install          # or npm/yarn
pnpm dev              # vite dev server on :5173
pnpm build            # tsc + vite build → dist/
pnpm preview          # serve dist/ locally
pnpm extract          # re-run extract-commands.mjs and extract-roles.mjs
pnpm deploy           # wrangler pages deploy dist/  (if using CF Pages)
```

### 5.6 Hosting

**Not a hosted site.** The Teach Skill ships inside the HERO package and is launched via:

```bash
hero teach
```

This starts a lightweight local HTTP server (Python `http.server` or Node `serve`), opens the default browser, and keeps the server alive until the tab is closed or 10 minutes of inactivity.

**Ship method:**
- Static build is bundled into the HERO Python package at `~/.hero/teach/`
- Installed during `pip install hero` (the build artefact is checked into the repo as a tarball, extracted on install)
- `hero teach` CLI command uses `webbrowser.open()` + a background server process
- No external hosting, no DNS, no analytics, no edge CDN
- Works fully offline after install

**Build artefact:**
- `pnpm build` → `dist/` → compressed into `hero-teach.tar.gz` → shipped inside the Python wheel
- On install, extracted to `~/.hero/teach/`
- Version tagged with HERO's version (teach v1.0.0 ships with hero v1.0.0)

---

## 6. Visual Design

### 6.1 Brand & mood

HERO is a **developer tool with military precision**. The visual language should feel:

- **Engineered, not decorative.** Sharp lines, no rounded everything. Generous use of monospace. Information density is a virtue.
- **Tactile, not glossy.** No gradients pretending to be materials. Solid colours with thin borders. The diagram should feel like a control panel.
- **Dark by default.** Most of our users live in a terminal. Dark mode is the homepage.
- **Restrained colour palette.** Score colours (emerald/amber/rose) do the heavy lifting. Brand colour is **emerald-500** (#22C55E) — "run green" from CLI culture.

### 6.2 🎨 Colour palette (from UI-UX-Pro-Max · Developer Tool / IDE)

**Dark theme (default):**

| Token | Hex | CSS Variable | Use |
|---|---|---|---|
| `bg-base` | `#0F172A` | `--color-background` | page background (slate-900) |
| `bg-elev-1` | `#1B2336` | `--color-card` | cards, panels |
| `bg-elev-2` | `#272F42` | `--color-muted` | hovered cards, code blocks |
| `border-subtle` | `#475569` | `--color-border` | dividers, node borders (idle) |
| `border-active` | `#22C55E` | `--color-accent` | node borders (running) — emerald-500 |
| `text-primary` | `#F8FAFC` | `--color-foreground` | body text |
| `text-muted` | `#94A3B8` | — | captions, labels |
| `accent` | `#22C55E` | `--color-accent` | "run green" — links, active states, pass |
| `pass` | `#22C55E` | — | emerald-500, score ≥70 |
| `warn` | `#FBBF24` | — | amber-400, score 50-69 |
| `fail` | `#EF4444` | `--color-destructive` | red-500, score <50 |
| `quarantine` | `#9F1239` | — | rose-800, dashed border |

**Why emerald-500 over cyan-400?** UI-UX-Pro-Max's Developer Tool / IDE product type ranks this palette first with the note "code dark + run green". For a CLI tool, green reads as "compile passed" / "test green" — a stronger semantic fit than cyan.

Contrast: `#0F172A` → `#F8FAFC` = 15.1:1 (WCAG AAA). Card `#1B2336` → text = 14.8:1. Muted `#94A3B8` on bg = 5.2:1 (AA). All pass.

**Light theme:**

| Token | Hex | Use |
|---|---|---|
| `bg-base` | `#FAFBFC` | page background |
| `bg-elev-1` | `#FFFFFF` | cards |
| `bg-elev-2` | `#F1F5F9` | hovered |
| `border-subtle` | `#E2E8F0` | dividers |
| `border-active` | `#16A34A` | emerald-600 |
| `text-primary` | `#0F172A` | body |
| `text-muted` | `#475569` | captions |
| `accent` | `#16A34A` | links, active |
| `pass` | `#059669` | emerald-600 |
| `warn` | `#D97706` | amber-600 |
| `fail` | `#DC2626` | red-600 |

### 6.3 🎨 Typography (from UI-UX-Pro-Max · Developer Mono pairing)

**Choice:** **JetBrains Mono** (headings + code) + **IBM Plex Sans** (body)

This is the "Developer Mono" pairing from the UI-UX-Pro-Max skill, ranked #1 for developer tools, documentation, code editors, and CLI apps. It scores 10/10 for: code, developer, technical, precise, functional, hacker mood.

| Role | Family | Weight | Size | Notes |
|---|---|---|---|---|
| **Display (h1)** | JetBrains Mono | 700 | 48/56 px | landing only, letter-spacing -1.5% |
| **Heading (h2-h3)** | JetBrains Mono | 600 | 28/20 px | monospace for structural headings |
| **Body** | IBM Plex Sans | 400 | 16/26 px | line-height 1.625 |
| **Code** | JetBrains Mono | 400 | 14/22 px | all code samples, terminal output |
| **Caption** | IBM Plex Sans | 500 | 13/18 px | muted, uppercase +1.2 tracking optional |
| **Score badge** | JetBrains Mono | 600 | 14/20 px | tabular figures for alignment |

Font loading: Both available via Google Fonts, self-hosted as woff2 in `/public/fonts/`. `font-display: swap`.

Tailwind config:
```js
fontFamily: {
  sans: ['IBM Plex Sans', 'sans-serif'],
  mono: ['JetBrains Mono', 'monospace'],
}
```

**Why not Inter?** Inter is the runner-up ("Modern Dark Cinema" pairing). It's a strong single-family system, but JetBrains Mono for headings gives the site a distinct "this is a developer tool" identity that Inter can't match. IBM Plex Sans has better legibility than Inter at small sizes.

### 6.4 Layout

- **Container width:** 1200 px max, centred, 24 px padding on mobile.
- **Grid:** 12-column on desktop, 4-column on tablet, 1-column on mobile.
- **Vertical rhythm:** 8 px base. Headings have 48 px top, 16 px bottom. Sections have 96 px between.
- **Sidebar:** right-side panel for the pipeline map detail; collapsible.

### 6.5 Mobile responsiveness

| Breakpoint | Behaviour |
|---|---|
| ≥ 1024 px | Full horizontal pipeline map. |
| 768–1023 px | Pipeline map wraps planning + execution into two stacked sections. |
| < 768 px | Pipeline map becomes a vertical scroll with sticky stage header. Tabs at the top to jump to a stage. |

The site must remain **fully readable on a phone** — code samples scroll horizontally, never truncate.

### 6.6 Accessibility

- All interactive elements reachable by keyboard. The pipeline map supports `Tab` between nodes and `Enter` to expand.
- `prefers-reduced-motion` disables pipeline animations and edge dashes.
- Colour is never the only signal — every status also has a text label or icon.
- WCAG 2.1 AA contrast ratios on text (≥ 4.5:1).
- Skip-to-content link for screen readers.

### 6.7 Imagery & icons

- **Icons:** **Lucide React** — open source, tree-shakeable, fits the engineering aesthetic.
- **Logos & avatars:** none in v1; reserve the spot.
- **Screenshots:** capture real `hero` output in a 1280×800 terminal (Alacritty on a dark theme), commit to `public/img/`.
- **No stock photos.** This is a developer tool — empty, decorative imagery is misleading.

### 6.8 Mockup descriptions (text-only)

**Landing page (desktop, dark mode):**
```
┌──────────────────────────────────────────────────────────────────────────┐
│  HERO  ▼   architecture · pipeline · commands · getting started  ☾ ⌥  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   HERO — a CLI that runs an army of AI agents across your projects.      │
│   Plan. Dispatch. Verify. Archive. One command, no babysitting.          │
│                                                                          │
│   [ Get Started → ]   [ See the Pipeline ]                              │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐   │
│   │  Council → Research → PE → Architect → Lead                     │   │
│   │                                          │                       │   │
│   │                                          ▼                       │   │
│   │  [PRE-COMMIT] → [BUILD] → [HARDEN] → [LEGAL] → [CI/PR] → ...   │   │
│   │   92          88          85         91        87       pass     │   │
│   │   ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔        │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ── What it does ──────────────────────────────────────────────────     │
│   ┌─ Discover ──────┐  ┌─ Orchestrate ──┐  ┌─ Verify ──────────┐          │
│   │ hero scan       │  │ Lead plans,    │  │ 7-stage gate      │          │
│   │ finds every     │  │ soldiers run   │  │ with DLQ on       │          │
│   │ project in      │  │ in parallel    │  │ failure           │          │
│   │ ~/Development   │  │ sandboxes.     │  │                   │          │
│   └─────────────────┘  └────────────────┘  └───────────────────┘          │
│                                                                          │
│   ── TOON vs JSON ───────────────────────────────────────────────────     │
│   ┌─ TOON (~40% fewer tokens) ─┐   ┌─ JSON ──────────────────┐            │
│   │ sandbox: sook-pro           │   │ {                       │           │
│   │ budget{...,tokens}:10k,0,9k│   │   "sandbox": "sook-pro" │           │
│   │ katana:                     │   │   "budget": { ... }     │           │
│   │   pending[0]:               │   │ }                       │           │
│   └─────────────────────────────┘   └─────────────────────────┘           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Architecture page (desktop, with side panel open):**
```
┌──────────────────────────────────────────────────────────────────────────┐
│  (same nav)                                                              │
├─────────────────────────────────────────────────────────────┬────────────┤
│  ┌────────────────────────────────────────────────────────┐  │  PRE-COMMIT│
│  │                                                        │  │            │
│  │   (pipeline map with all 12+ nodes, animated)          │  │  What:     │
│  │                                                        │  │  secrets + │
│  │   ── current node highlighted with cyan border ──      │  │  lint +    │
│  │                                                        │  │  copyright │
│  │   [minimap] [+] [−] [Replay]                           │  │            │
│  │                                                        │  │  Who:      │
│  └────────────────────────────────────────────────────────┘  │  soldier   │
│                                                             │  (step-3.5) │
│  ── Side rail ─────────────────────────────────────────────  │            │
│  ┌─ Sandbox isolation ─┐ ┌─ Exchange Layer ─┐ ┌─ Reliability ┐  │  Score:    │
│  │ one project = one   │ │ soldiers talk via│ │ DLQ, CB,    │  │  92 / 100  │
│  │ dir under ~/.hero/  │ │ .toon in  ~/.../ │ │ budgets     │  │            │
│  │                     │ │ exchange/        │ │             │  │  View →    │
│  └─────────────────────┘ └──────────────────┘ └─────────────┘  │  source    │
└─────────────────────────────────────────────────────────────┴────────────┘
```

---

## 7. Implementation Plan

### 7.1 Phases

**Phase 0 — Skeleton (½ day)**
- Scaffold Vite + React + TS + Tailwind.
- Set up routing with placeholder pages.
- Theme toggle (dark default, light opt-in, system-aware).
- Layout: nav, footer, container, typography scale.
- Deploy a "Hello, HERO" preview to Cloudflare Pages to lock in the pipeline.

**Phase 1 — Pipeline map (1–2 days)**
- Build `PipelineMap`, `NodePill`, `NodePanel` components.
- Author `pipeline.json` with all 12+ nodes and edges.
- Wire up the 3 surfaces (landing, architecture, pipeline).
- Animate edge dashes and node pulse.
- Side panel: what/who/score/example content per node.

**Phase 2 — Content (2–3 days)**
- Write all MDX pages: landing, architecture, pipeline, exchange, roles, getting-started, examples, learn, about.
- Build the command extractor script; emit `commands.json`.
- Build the role extractor; emit `roles.json`.
- Author 3–5 example runs with real `hero` output.
- TOON vs JSON side-by-side widget.

**Phase 3 — Polish (1 day)**
- Keyboard navigation on the pipeline map.
- `prefers-reduced-motion` handling.
- SEO meta tags per page.
- OpenGraph image generation.
- Lighthouse pass: target ≥ 95 on every category.

**Phase 4 — Launch (½ day)**
- Final review with the user.
- Cut a `v1.0.0` release tag.
- Production deploy.
- Announcement post (Discord / blog / README link).

**Total: ~5 working days for one developer.** Spread over 1–2 weeks for a part-time contributor.

### 7.2 Dependencies on the user

The user (HERO maintainer) needs to:

1. Confirm the brand colour is acceptable (cyan-400).
2. Provide 3–5 real `hero` terminal output snippets to embed.
3. Approve the 3 canonical example runs (e.g. "fix theme switcher lag in sook-pro").
4. Provide a logo or confirm "HERO" wordmark is fine.
5. Confirm the hosting choice (Cloudflare Pages recommended).
6. Confirm the custom domain.

### 7.3 Risks and mitigations

| Risk | Mitigation |
|---|---|
| Pipeline map becomes too complex to read | Two zoom levels: "summary" (4-5 nodes) and "full" (all 12+). User can collapse planning vs execution. |
| Command reference drifts from `src/hero/commands/` | `pnpm extract` is part of CI — site fails to build if it can't parse the latest source. |
| Animations distract on mobile | `prefers-reduced-motion` and a "static" toggle in the UI. |
| Bundle size creeps up | React Flow is the only heavy dep. Code-split per route. Budget: < 200 KB gzipped initial JS. |
| Hosting cost surprises | Cloudflare Pages free tier covers this use case for years. |

### 7.4 Out of scope for v1

- User accounts / saved pipelines.
- Live "Run a pipeline" demo in the browser (mock the output instead).
- i18n (English only in v1; structure allows translation later).
- Blog / changelog (link to GitHub releases for now).
- Search across all docs (we ship command search; full-text search is a v2).

---

## 8. Success Metrics

### 8.1 Launch criteria (must-have)

- [ ] All 10+ pages render without console errors.
- [ ] Lighthouse: Performance ≥ 95, Accessibility ≥ 95, Best Practices ≥ 95, SEO ≥ 95.
- [ ] `pnpm build` succeeds in < 60s.
- [ ] Total JS bundle < 200 KB gzipped.
- [ ] All code samples are real and runnable against the current `main` branch of HERO.
- [ ] Pipeline map renders identically across Chrome, Firefox, Safari.
- [ ] Mobile layout passes manual testing on iPhone SE (375 px wide) and Pixel 5.
- [ ] Theme toggle persists across reloads.
- [ ] Site loads over 3G in < 3s.

### 8.2 Adoption signals (30-day post-launch)

| Signal | Target |
|---|---|
| Unique visitors (Plausible) | ≥ 200 / week within 30 days |
| Time on `/architecture` | median ≥ 90s (proves the map is being explored) |
| Bounce rate on `/` | < 50% |
| "Get Started" CTA click-through | ≥ 25% of landing visitors |
| GitHub stars attributed to site referrals | measurable in UTM |
| Discord/community mentions of the site | qualitative — "I sent someone the HERO teach site" |

### 8.3 Content health (quarterly review)

- [ ] All 30+ commands still documented; deprecated commands marked.
- [ ] Pipeline map reflects current stages (PRE-COMMIT → ARCHIVE) and any new roles.
- [ ] Exchange Layer page matches the latest `EXCHANGE_LAYER_SPEC.md`.
- [ ] Example outputs regenerated against latest HERO.
- [ ] No 404s from the deploy logs.

### 8.4 Maintenance load

- **Weekly:** review and merge community PRs (typos, broken examples).
- **Monthly:** regenerate `commands.json` and `roles.json` against latest source; verify example outputs.
- **Quarterly:** content review; new screenshot; update roadmap.

The site is built so that most maintenance is mechanical — the extractor scripts ensure documentation can't drift silently.

---

## 9. Open questions for the user

**Already answered by UI-UX-Pro-Max refinement:**
1. ✅ **Brand colour** — emerald-500 (#22C55E) "run green", sourced from Developer Tool / IDE palette. Replaces cyan-400.
2. ✅ **Typography** — JetBrains Mono (headings) + IBM Plex Sans (body). Replaces Inter.
3. ✅ **Delivery** — `hero teach` CLI command launches local server with static site. No external hosting.
4. ✅ **Analytics** — None (local-only site). No tracking.

**Still need your input:**
5. **Domain / serve path** — default is `http://localhost:9099`. Do you want a custom port, or auto-select? Also: should `hero teach` open the system browser automatically?
6. **Logo** — is the "HERO" wordmark sufficient, or do you have a logo SVG to embed?
7. **Example runs** — which 3–5 real `hero` runs do you want featured on `/examples`? Need real terminal output to capture.
8. **i18n** — English only for v1, confirmed?
9. **Emoji in content** — UI-UX-Pro-Max says no emoji as icons. Are terminal emojis (✅, 🟢, 🔴) okay inside code samples (they're data, not UI icons)?

---

## 10. Appendix — file index

This document lives at `/home/max/Development/HERO/docs/TEACH_SKILL_DESIGN.md`.
Its companion build brief lives at `/home/max/Development/HERO/docs/TEACH_SKILL_BUILD.md`.

**Source files referenced:**
- `SPEC.md` — system specification
- `README.md` — current user-facing docs
- `docs/PIPELINE.md` — pipeline flow
- `docs/EXCHANGE_LAYER_SPEC.md` — exchange layer
- `src/hero/cli.py` — registered commands
- `src/hero/commands/*.py` — command implementations
- `src/hero/exchange/*.py` — exchange layer
- `~/.hero/army.yaml` — roles and models

**Generated artefacts referenced:**
- `src/data/commands.json` — extracted at build time
- `src/data/roles.json` — extracted at build time
- `src/data/pipeline.json` — hand-authored

**Implementation brief companion:** `TEACH_SKILL_BUILD.md`.

---

**Last updated:** 2026-06-07
