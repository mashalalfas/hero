# LEAD_BRIEF — HERO Viewport v3: Cyber-Glass Overhaul

## Mission
Transform the HERO web dashboard from a functional-but-plain vanilla JS app into a **Cyber-Glass** command center. Midnight Command color palette, bento grid layout, glassmorphism effects, modular ES architecture, and full control features (kill/spawn). No frameworks, no build step — pure vanilla JS ES modules.

## Current State
- `server.py`: FastAPI, serves `static/` at `/static/`, has `/api/v1/tree`, `/summary`, `/sandbox/{name}`, `/sandbox/{name}/timeline`, `/bottlenecks`, `/events` (SSE). Auth via `HERO_WEB_TOKEN` Bearer check. **No kill/control endpoints yet.**
- `static/index.html`: Shell loading `style.css` + `app.js`
- `static/app.js`: 637-line monolith — SSE, fetch, tree render, sparkline, drawer, search, filters, all in one file
- `static/style.css`: 917 lines, dark theme with CSS vars
- `static/components/`: Empty directory

## Target Architecture

```
static/
├── index.html              ← REWRITE: new shell with module imports
├── css/
│   ├── tokens.css          ← Design tokens (Midnight Command palette)
│   ├── base.css            ← Reset, typography, scrollbar, selection
│   ├── layout.css          ← Bento grid, responsive breakpoints
│   ├── components.css      ← Cards, badges, pills, drawer, modal, toast
│   └── animations.css      ← Keyframes, transitions, glow effects
├── js/
│   ├── app.js              ← Entry: init, wire modules, mount
│   ├── services/
│   │   ├── api.js          ← Fetch wrappers for all endpoints
│   │   ├── sse.js          ← EventSource + reconnect wrapper
│   │   ├── state.js        ← Centralized reactive state
│   │   └── auth.js         ← Token management (sessionStorage)
│   ├── components/
│   │   ├── header.js       ← Top bar with live indicator + controls
│   │   ├── stats-bar.js    ← Token count, active count, burn gauge
│   │   ├── sandbox-card.js ← Bento tile: tree + status + controls
│   │   ├── tree-node.js    ← Recursive tree renderer
│   │   ├── detail-panel.js ← Drawer/modal with sandbox details
│   │   ├── timeline.js     ← Event timeline visualization
│   │   ├── sparkline.js    ← SVG sparkline component
│   │   ├── controls.js     ← Kill/confirm action buttons
│   │   ├── toast.js        ← Notification toast system
│   │   └── modal.js        ← Confirmation modal
│   └── utils/
│       └── dom.js          ← escapeHtml, escapeAttr, createElement helpers
├── app.js                  ← DELETE (replaced by js/app.js)
└── style.css               ← DELETE (replaced by css/)
```

## 4 Implementation Waves

### Wave 1: Foundation (Design System + API Layer)
**Soldiers:** Design System, API Layer — **parallel, no dependencies**

- **Soldier 1 — Design System:** Create `css/tokens.css`, `css/base.css`, `css/layout.css`, `css/components.css`, `css/animations.css`
- **Soldier 2 — API Layer:** Create `js/services/api.js`, `js/services/sse.js`, `js/services/state.js`, `js/services/auth.js`, `js/utils/dom.js`

### Wave 2: Components (Build on Wave 1)
**Soldier:** Components — depends on Wave 1 design tokens + API services

- **Soldier 3 — Components:** Create all `js/components/*.js` files. Each exports a `create()`, `update()`, `destroy()` lifecycle.

### Wave 3: Control Features + Polish
**Soldiers:** Control Features, Futuristic Polish — **parallel**

- **Soldier 4 — Control Features:** Add `POST /api/v1/sandbox/{name}/kill` endpoint to `server.py`. Create `controls.js` + `modal.js` confirmation flow. Bearer token + confirmation token required.
- **Soldier 6 — Futuristic Polish:** Glassmorphism effects, animation system, glow, particle system, font integration (Orbitron + Share Tech Mono)

### Wave 4: Mobile + Integration
**Soldiers:** Mobile Responsive + Integration — **parallel after Wave 3**

- **Soldier 5 — Mobile Responsive:** Responsive bento grid, touch targets ≥44px, collapsible sections, safe area insets
- **Soldier 7 — Integration:** Rewrite `index.html` + `js/app.js` entry point. Wire all modules. Delete old `app.js` and `style.css`.

## Spawn Order
```
Wave 1 (parallel):
  → Soldier 1: Design System
  → Soldier 2: API Layer

Wave 2 (after Wave 1):
  → Soldier 3: Components

Wave 3 (parallel, after Wave 2):
  → Soldier 4: Control Features
  → Soldier 6: Futuristic Polish

Wave 4 (after Wave 3):
  → Soldier 5: Mobile Responsive
  → Soldier 7: Integration (app.js + index.html rewrite + cleanup)
```

## Verification Strategy
1. **Per-soldier:** Each soldier includes ACCEPTANCE criteria in their brief
2. **Integration test:** After all waves, serve the app (`python -m hero.web.server`) and verify:
   - `/` loads the new dashboard (not the old one)
   - `/api/v1/tree` returns data and dashboard renders it
   - SSE connection established (check Network tab)
   - Bento grid renders correctly at 1920px, 1024px, 768px, 375px
   - Kill button shows confirmation modal, sends Bearer token
   - Glassmorphism effects visible (backdrop-filter blur)
   - Fonts load (Orbitron headings, Share Tech Mono data)
   - Animations smooth (no jank, 150-300ms transitions)
3. **Regression:** All existing API routes still work unchanged
4. **No build step:** Open `index.html` in browser, everything works

## Key Constraints
- **No frameworks** — vanilla JS only, ES modules via `<script type="module">`
- **No build step** — no webpack, no vite, no bundler
- **Keep existing API routes** — add new ones, don't break old ones
- **Bearer token auth** — all API calls include `Authorization: Bearer <token>` from sessionStorage
- **Colors:** Midnight Command palette — `#0a0a0f` bg, `#00f0ff` accent, `#ff003c` danger, `#00ff88` success
- **Fonts:** Orbitron (headings), Share Tech Mono (data/mono), system sans for body
- **Animations:** 150ms micro, 300ms standard, 500ms emphasis — `cubic-bezier(0.4, 0, 0.2, 1)`
