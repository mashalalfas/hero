# COUNCIL_ANALYSIS.md — HERO Web Dashboard Redesign

**Analyst:** HERO Army Council Analyst  
**Date:** 2026-05-27  
**Status:** Analysis Complete

---

## 1. Gap Analysis: Current vs Vision

### 1.1 Vision: "Which project is actively working"

| Current | Gap |
|---|---|
| Shows all sandboxes in a flat tree view with status badges | No "most active" highlighting — all cards look equal |
| Auto-expands active sandboxes in state.expanded | Cards ranked by index order, not by activity |
| SSE refreshes summary every 2s | No visual priority for actively-working sandboxes |
| Status dot animation (pulse) for active sandboxes | Active state is subtle — easy to miss on mobile |

**Requirement:** Active sandboxes must be visually dominant — larger, glowing, ranked-first, pinned to top.

### 1.2 Vision: "Token burn per project"

| Current | Gap |
|---|---|
| Total tokens in stats bar + per-sandbox budget in drawer sparkline | No **per-project burn rate** visualization |
| `calcBurnRate()` / `compute_budget_projections()` exist in backend | Burn rate only shown in sparkline pill as `N t/min` aggregate |
| Budget projection (ETA, status) exists in `intel.py` | NOT exposed via any API endpoint |
| Token history array (30 samples) in `state.tokenHistory` | Only one sparkline for aggregate, none per sandbox |
| Per-sandbox data available via `/api/v1/sandbox/{name}` | No `/api/v1/burn-rates` or `/api/v1/budget-projections` endpoint |

**Requirement:** Per-sandbox burn-rate gauge, budget projection cards, a historic burn-rate chart (area/sparkline per sandbox), and an army-level "burn dashboard" view.

### 1.3 Vision: "Which agents flunked out / failed"

| Current | Gap |
|---|---|
| Status badges show error/red for failed agents | No **dedicated "Failed" view** — failed sandboxes mixed with active/idle |
| Bottleneck API detects error cascades (retry_count > 2) | Not displayed in the UI at all — no bottleneck panel/zone |
| `/api/v1/bottlenecks` endpoint exists | Frontend fetches but never renders bottleneck data |
| `state.errorCount` tracked | Only shown as a number in stats bar — no context, no list |
| Detail drawer shows errors if present | Must click individual sandbox to see errors |

**Requirement:** A dedicated "Failed / Stuck" zone — cards/warnings for errored agents, error cascades, and circuit-breaker quarantines. Red-glowing indicators. Actionable "retry" or "kill" buttons.

### 1.4 Vision: "Where the system is stuck"

| Current | Gap |
|---|---|
| Pipeline stall detection in `intel.py` (zero tool calls >30s) | NOT surfaced in the UI at all |
| `no_progress_counter` tracked per sandbox | Not visible without opening drawer |
| Circuit breaker quarantine detection | Not displayed to user |
| `/api/v1/bottlenecks` exists | Not consumed by frontend |

**Requirement:** A "Stuck Agents" panel — pipeline stalls, quarantined sandboxes, budget-critical agents. Suggestion cards with remediation actions.

### 1.5 Vision: "Control features (kill, spawn, dispatch)"

| Current | Gap |
|---|---|
| `hero kill` CLI command exists (updates `SandboxState`, archives dispatch) | **No API endpoint** — web dashboard cannot kill |
| `hero spawn` / `dispatch.enqueue()` exists | **No API endpoint** for spawning from web |
| `hero go` full pipeline exists | **No API endpoint** for dispatching tasks |
| Bearer token auth (`_check_auth`) already in place | Auth ready for control endpoints |
| `SoldierSpawner` class in `soldier/spawner.py` | No HTTP wrapper around it |

**Requirement:** POST /api/v1/sandbox/{name}/kill, POST /api/v1/sandbox/{name}/spawn, POST /api/v1/dispatch endpoints. Confirmation modals on the frontend. Auth-gated.

---

## 2. Design Language Recommendations

Using the UI/UX Pro Max skill framework for a "Futuristic, next-level dashboard":

### 2.1 Style: Cyber-Glass (Glassmorphism + Neon)

- **Primary pattern:** Glassmorphism on cards (`backdrop-filter: blur(16px)`, `background: rgba(17, 24, 39, 0.7)`, `border: 1px solid rgba(255,255,255,0.06)`)
- **Secondary pattern:** Subtle grid background (`repeating-linear-gradient` at 30px intervals, opacity 0.03)
- **Accent glow:** Neon cyan (`#06b6d4`) and purple (`#a855f7`) gradient borders on active cards
- **Surface structure:** Bento grid layout — irregular card sizes based on importance

### 2.2 Color System

| Token | Current | Recommended |
|---|---|---|
| `--bg-deepest` | `#05080f` | `#020408` (even deeper — cosmic black) |
| `--bg` | `#0a0e17` | `#060b14` |
| `--bg-surface` | `#111827` | `rgba(17, 24, 39, 0.85)` + backdrop blur |
| `--accent` | `#3b82f6` | `#06b6d4` (cyan) with `#a855f7` (purple) gradient |
| `--green` | `#22c55e` | Keep — works well |
| `--red` | `#ef4444` | Keep — works well |
| `--yellow` | `#eab308` | Keep — works well |
| New | — | `--glow-cyan: 0 0 20px rgba(6,182,212,0.15)` |
| New | — | `--glow-purple: 0 0 20px rgba(168,85,247,0.15)` |
| New | — | `--glow-red: 0 0 20px rgba(239,68,68,0.2)` |

### 2.3 Typography

- **Headings:** Inter Bold 800 — already used, keep it
- **Body:** Inter Regular 400 — already used, keep it
- **Monospace:** JetBrains Mono — already loaded, keep it
- **New:** Add `font-feature-settings: "cv02","cv05","cv08"` for Inter stylistic alternates (more futuristic feel)
- **Scale enforment:** Apply strict type scale: `12 / 14 / 16 / 18 / 24 / 32 / 48`

### 2.4 Animation Guidelines

| Element | Duration | Easing | Notes |
|---|---|---|---|
| Card hover glow | 200ms | ease-out | Scale 1.02 + glow border |
| Status transitions | 300ms | cubic-bezier(0.4, 0, 0.2, 1) | Smooth state change |
| Detail drawer | 250ms | ease-out | Slide from right |
| New sandbox appear | 300ms | ease-out | Fade + slide up |
| Failed agent alert | 400ms with pulse | — | Subtle red pulse, then steady |
| Modal confirm | 200ms | ease-out | Scale 0.96→1.0 |
| Skeleton loading | — | shimmer | Loading shimmers on first load |

### 2.5 What To Replace

**Emoji icons → SVG icons.** Current dashboard uses emoji as structural icons:
- `⚡` → Lightning bolt SVG (active indicator)
- `🎯` → Target SVG (LEAD)
- `🏗️` → Construction SVG (ARCH)
- `🤖` → Robot SVG (SOLDIER)
- `🔍` → Search SVG (VERIFY)
- `📦` → Package SVG (ARCHIVE)
- `📭` → Mail SVG (empty state)
- `⚠` → Warning SVG (error state)

All must be replaced with inline SVG or a lightweight icon set. Lucide icons (MIT, tree-shakeable) are recommended.

---

## 3. Control Features: Feasibility Assessment

### 3.1 Kill Sandbox — HIGH feasibility, LOW cost

**Backend needed:** Single POST endpoint

```python
@app.post("/api/v1/sandbox/{name}/kill")
async def api_kill_sandbox(name: str, request: Request):
    _check_auth(request)
    from hero.state.sandbox import SandboxState
    from hero.state.index import IndexState
    
    ss = SandboxState(name)
    ss.update_status("dead")
    
    index = IndexState()
    entry = index.get_sandbox(name)
    if entry:
        index_data = index.load()
        for sb in index_data.get("sandboxes", []):
            if sb.get("name") == name:
                sb["status"] = "dead"
                break
        index.save(index_data)
    
    return JSONResponse({"status": "dead", "sandbox": name})
```

**Frontend:** "Kill" button in sandbox card header, confirmation modal.

### 3.2 Spawn Agent — HIGH feasibility, MEDIUM cost

**Backend needed:** POST endpoint with form body

```python
@app.post("/api/v1/sandbox/{name}/spawn")
async def api_spawn(name: str, request: Request):
    _check_auth(request)
    body = await request.json()
    task = body.get("task")
    role = body.get("role", "soldier")
    budget = body.get("budget", 5000)
    
    from hero.soldier.dispatch import enqueue
    task_id = enqueue(
        sandbox=name,
        task=task,
        role=role,
        budget=budget
    )
    return JSONResponse({"task_id": task_id, "status": "queued"})
```

**Frontend:** "Spawn" button → modal with task input, role dropdown, budget slider.

### 3.3 Dispatch Tasks — HIGH feasibility, MEDIUM cost

**Backend needed:** POST `/api/v1/dispatch` endpoint

```python
@app.post("/api/v1/dispatch")
async def api_dispatch(request: Request):
    _check_auth(request)
    body = await request.json()
    from hero.soldier.dispatch import enqueue
    task_ids = []
    for item in body.get("tasks", []):
        tid = enqueue(
            sandbox=item["sandbox"],
            task=item["task"],
            role=item.get("role", "soldier"),
            budget=item.get("budget", 5000),
        )
        task_ids.append(tid)
    return JSONResponse({"task_ids": task_ids, "count": len(task_ids)})
```

**Frontend:** Bulk dispatch panel — multi-sandbox task creation.

### 3.4 Auth Considerations

Already exists: `HERO_WEB_TOKEN` env var → Bearer token check. Control endpoints MUST use the same auth (or stricter, like a separate `HERO_WEB_ADMIN_TOKEN`). Note: token check currently called on all endpoints, so it's already gated.

### 3.5 Risk: Idempotency

- Kill on already-dead sandbox: Safe, just no-op. Already handled in CLI.
- Spawn into non-existent sandbox: Need index check before enqueueing.
- Concurrent spawns: Dispatch queue naturally serializes. No race condition.
- Kill during active pipeline: Current `hero kill` archives dispatch tasks to DLQ — web endpoint should do the same.

### 3.6 Risk: User Error

- Accidental kill: Need confirmation modal (`Are you sure? X pending tasks will be archived`).
- Accidental mass spawn: Rate-limit the spawn endpoint (max 3 concurrent per sandbox).
- Budget exhaustion from over-spawning: Pre-check tokens_remaining before accept.

---

## 4. Key Risks & Edge Cases

### 4.1 Frontend Risk: Bundle Size

Current `app.js` is ~24KB. The redesign will add:
- Charting library (Chart.js or lightweight canvas)
- SVG icon set inline
- Bottleneck/stuck/control UIs
- SPA-style navigation/routing

**Mitigation:** Keep it vanilla JS. Use a lightweight canvas chart (e.g. uPlot, <10KB). Inline only the SVG icons actually used (maybe 15-20 icons). Avoid React/Vue/Svelte — the bundle overhead isn't justified for a single-page dashboard.

### 4.2 Frontend Risk: Mobile Performance

Current responsive is basic (640px breakpoint). Adding animations, glassmorphism, and a chart on mobile could cause jank.

**Mitigation:** 
- Use `will-change: transform` only on animated elements
- Reduce blur radius on mobile (`backdrop-filter: blur(8px)` vs `16px`)
- Charts: simplify on mobile (remove gridlines, reduce tick count)
- Disable particle/background effects on <768px
- Test on actual phone hardware

### 4.3 Backend Risk: SSE Overload

Current SSE pushes every 2s. Adding bottleneck/chart data will increase payload size.

**Mitigation:** The new endpoints (`/api/v1/burn-rates`, `/api/v1/bottleneck-summary`) should be polled at lower frequency (every 10-15s) while `/api/v1/events` keeps the 2s SSE for active status. Separate the data streams by update frequency.

### 4.4 Backend Risk: Control Endpoint Security

Adding control endpoints (kill, spawn) to a dashboard accessible from phone on WiFi means:
- Bearer token sent in each request
- Token could be intercepted on local WiFi
- CSRF-like attacks from other websites on same network

**Mitigation:**
- `HERO_WEB_TOKEN` must be set (error if missing + control endpoint called)
- Consider separating `HERO_WEB_ADMIN_TOKEN` for write operations
- Add rate-limiting on control endpoints
- Log all control actions with timestamp + IP
- CORS already allows `*` — restrict to specific origins if needed

### 4.5 Edge Case: Zero Sandboxes

Current dashboard shows empty state. The redesign must handle:
- Fresh install (no sandboxes)
- All sandboxes dead
- Single sandbox
- 20+ sandboxes

**Mitigation:** Test all states. Empty state should include a "getting started" prompt. Large counts should use virtual scrolling or pagination.

### 4.6 Edge Case: Network Loss

SSE auto-reconnects. Fetch calls fail silently. The dashboard could show stale data for a long time.

**Mitigation:** Add a "connection status" indicator (green dot → red dot when SSE drops). Show a stale-data warning banner if >5s since last update. Add a manual refresh button. Disable control buttons when offline.

### 4.7 Edge Case: Very Long Sandbox Names

Current truncation is `max-width: 300px` CSS-only. Long names could break layout in bento grid.

**Mitigation:** Use `text-overflow: ellipsis` with a tooltip on hover. Define max name length (30 chars) or truncate gracefully.

---

## 5. Priority Ranking of Features

### P0 — Must Have (Prerequisite for everything else)

| # | Feature | Effort | Impact | Notes |
|---|---|---|---|---|
| 1 | **Active-project spotlight** | 1-2 days | High | Card ranking, glow border, auto-pin active |
| 2 | **Failed/stuck agent panel** | 2-3 days | High | Consume `/api/v1/bottlenecks`, red zone, error cascade cards |
| 3 | **Per-sandbox burn rate gauge** | 2-3 days | High | Expose `compute_budget_projections()` via new endpoint, mini gauges on cards |

### P1 — Should Have

| # | Feature | Effort | Impact | Notes |
|---|---|---|---|---|
| 4 | **Design system overhaul** | 3-4 days | High | Glassmorphism, bento grid, glow effects, SVG icons |
| 5 | **"Kill sandbox" button** | 1 day | High | POST `/api/v1/sandbox/{name}/kill`, confirmation modal |
| 6 | **Mobile-first responsive** | 2-3 days | High | Bento stack on mobile, simplified charts, touch-friendly |

### P2 — Nice to Have

| # | Feature | Effort | Impact | Notes |
|---|---|---|---|---|
| 7 | **"Spawn agent" modal** | 2-3 days | Medium | POST endpoint, task input form, role dropdown |
| 8 | **Bottleneck suggestion cards** | 1-2 days | Medium | Recommendation pills with one-click "apply" |
| 9 | **Bulk dispatch panel** | 2-3 days | Medium | Multi-sandbox task creation |
| 10 | **Historic burn chart** | 2-3 days | Medium | 30-minute window area chart per sandbox |

### P3 — Stretch

| # | Feature | Effort | Impact | Notes |
|---|---|---|---|---|
| 11 | **Particle/starfield background** | 1-2 days | Low | Visual flair only — respect reduced-motion |
| 12 | **Dark/light mode toggle** | 1 day | Low | Low priority since already dark-only |
| 13 | **Sandbox comparison view** | 3-4 days | Low | Side-by-side budget, burn rate, errors |
| 14 | **WebSocket upgrade** | 2-3 days | Low | Replace SSE with WS for bidirectional comm (needed for control feedback) |
| 15 | **Action logs / audit trail** | 1-2 days | Low | Show recent kill/spawn/dispatch actions with undo |

---

## 6. Recommended Implementation Order

### Phase 1 (Days 1-2) — Foundation + P0
1. Add `/api/v1/budget-projections` endpoint exposing `compute_budget_projections()`
2. Add `/api/v1/bottleneck-summary` endpoint (aggregated, UI-friendly)
3. Add failed/stuck agent panel to frontend
4. Rank sandbox cards by activity (active first, red-bordered last)

### Phase 2 (Days 3-5) — Design + Responsive
5. Apply glassmorphism surface redesign (CSS tokens, backdrop blur)
6. Bento grid layout for responsive stacking
7. Replace emoji icons with inline Lucide SVGs
8. Add per-sandbox mini burn-rate gauge
9. Mobile-first testing & polish

### Phase 3 (Days 6-7) — Control Features
10. Add POST `/api/v1/sandbox/{name}/kill` endpoint
11. Add "Kill" button with confirmation modal
12. Add POST `/api/v1/sandbox/{name}/spawn` endpoint
13. Add "Spawn" modal with task input + role selector
14. Add POST `/api/v1/dispatch` for bulk dispatch

### Phase 4 (Days 8-10) — Polish + Stretch
15. Animated transitions (card entry/exit, status changes)
16. Bottleneck suggestion cards with one-click actions
17. Historic burn-rate charts
18. Particle background (if time allows)
19. Security hardening, rate limiting, logging

---

## 7. Backend API Contract (New Endpoints)

| Method | Endpoint | Request Body | Response | Purpose |
|---|---|---|---|---|
| GET | `/api/v1/budget-projections` | — | `[{sandbox, tokens_used, tokens_budget, usage_pct, burn_rate, eta_minutes, status}]` | Per-sandbox burn projections |
| GET | `/api/v1/bottleneck-summary` | — | `{count, critical: [...], warning: [...], actions: [...]}` | Aggregated for UI |
| POST | `/api/v1/sandbox/{name}/kill` | `{force?: bool, archive_tasks?: bool}` | `{status, sandbox}` | Kill sandbox |
| POST | `/api/v1/sandbox/{name}/spawn` | `{task, role?, budget?}` | `{task_id, status}` | Spawn agent |
| POST | `/api/v1/dispatch` | `{tasks: [{sandbox, task, role?, budget?}]}` | `{task_ids, count}` | Bulk dispatch |

---

*Analysis prepared by HERO Army Council Analyst. Ready for Council deliberation and Architect breakdown.*
