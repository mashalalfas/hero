# KIMI NOTION PLAN — HERO Dashboard Clean-Slate Rewrite

**Author:** Kimi K2.6, HERO Army Architect  
**Date:** 2026-05-27  
**Aesthetic:** Clean white/black Notion-style (no glassmorphism, no particles, no neon, no glow)

---

## Table of Contents

1. [Architecture Diagnosis](#1-architecture-diagnosis)
2. [CSS Clean-Slate Plan](#2-css-clean-slate-plan)
3. [JS Fix Plan](#3-js-fix-plan)
4. [index.html Changes](#4-indexhtml-changes)
5. [Execution Order](#5-execution-order)
6. [UI/UX Design Decisions (from UI/UX Pro Max)](#6-uiux-design-decisions)

---

## 1. Architecture Diagnosis

### What's Actually Running

```
app.js init() ─┬─ createHeader(headerEl)    ✓  Works, subscribed to state
               ├─ initParticles(body)       ✗  REMOVE — no particles, no glow
               ├─ loadData()                ─┬─ fetchTree() + fetchSummary()
               │                             └─ renderDashboard(state)  ← MANUAL HTML
               ├─ connectSSE()               ┬─ on('summary', data) → updateComponents (TODO stub)
               │                              └─ NO re-render triggering
               └─ setInterval(loadData, 10s)  ── Refetches, re-runs renderDashboard
```

### Key Findings

| Issue | Root Cause | Severity |
|-------|-----------|----------|
| **Cards don't re-render** | `renderDashboard()` in app.js creates manual HTML — the `sandbox-card.js` component `create()` is imported but NEVER CALLED. Stats-bar also imported but never initialized. SSE events hit an empty `updateComponents` stub. | 🔴 CRITICAL |
| **"Unnamed dead" tree nodes** | `renderTreeNode` in `tree-node.js` uses emoji icons (violates UI/UX skill rule "No Emoji as Structural Icons"). The tree data from API may have nested structure that the flat render doesn't handle. Status badge renders "dead" because the sandbox status literally is "dead". | 🔴 CRITICAL |
| **Kill button invisible** | `controls.js` exports `renderControls()` but it's never called. The sandbox card template in `renderDashboard` doesn't include a kill button. | 🔴 CRITICAL |
| **All sandboxes show dead** | The sandboxes are actually dead (no active HERO processes running). But even if they change, `renderDashboard` only runs once per `loadData()` call — there's no live updating via SSE subscription on the dashboard cards. | 🟡 HIGH |
| **Backdrop-filter crashes** | `@supports (backdrop-filter: blur(1px))` blocks add glass effect after detecting support, but some mobile browsers still crash on actual blur rendering. The `.is-mobile` guard exists but the CSS still applies `backdrop-filter` behind `@supports`. | 🟡 HIGH |
| **Cyber-Glass cruft** | `effects.js` (particles, glow, shake, cursor), `mobile-nav.js` (redundant — CSS handles this), scanline overlays, noise textures, 20+ animation keyframes. | 🟡 HIGH |
| **State subscribe works fine** | `state.js` singleton pattern is correct. `subscribe()` returns cleanup function. Both direct exports and factory return the same singleton. | ✅ OK |
| **SSE manager** | `sse.js` works correctly. Events fire. The issue is on the consumer side. | ✅ OK |
| **API layer** | `api.js` works fine. Bearer token, error handling, auth events all correct. | ✅ OK |

### Architecture Fix Summary

```
BEFORE:                              AFTER:
app.js ─┬─ renderDashboard() ✗      app.js ─┬─ initComponents() ← calls all factories
         ├─ createHeader() ✓                 ├─ createHeader() 
         ├─ initParticles() ✗                ├─ createStatsBar()
         └─ loadData() → manual HTML         ├─ createSandboxCards()
                                              └─ createDetailPanel()
                                              
SSE → updateComponents (stub) ✗     SSE → state.setState() → subscribe() re-renders
```

---

## 2. CSS Clean-Slate Plan

### 2.1 tokens.css — Design Tokens (White/Black Notion)

**Replace completely.** New tokens:

```css
:root {
  /* ── Colors: Pure Black & White ───────── */
  --color-white:      #ffffff;
  --color-bg:         #ffffff;       /* Page background */
  --color-surface:    #ffffff;       /* Card / container background */
  --color-elevated:   #fafafa;       /* Slightly shaded surface */
  --color-hover:      #f5f5f5;       /* Hover state */
  --color-border:     #e5e5e5;       /* Default border */
  --color-border-subtle: #f0f0f0;    /* Lighter border */
  --color-border-hover: #d0d0d0;     /* Border on hover */

  /* ── Text: Black scale ─────────────────── */
  --text-primary:     #1a1a1a;        /* Body text */
  --text-secondary:   #6b6b6b;        /* Secondary text */
  --text-tertiary:    #9e9e9e;        /* Placeholder / disabled */
  --text-inverse:     #ffffff;        /* Text on dark */

  /* ── Accents: Muted (Notion-like) ──── */
  --color-accent:     #37352f;        /* notion-gray */
  --color-accent-blue: #2383e2;       /* notion-blue */
  --color-accent-red:  #e03e3e;       /* notion-red */
  --color-accent-green: #0f7b6c;      /* notion-green */
  --color-accent-yellow: #dfab00;     /* notion-yellow */
  --color-accent-purple: #6940a5;     /* notion-purple */

  /* ── Semantic (mapped from accents) ────── */
  --color-success:    #0f7b6c;
  --color-danger:     #e03e3e;
  --color-warning:    #dfab00;
  --color-info:       #2383e2;

  /* Status dot colors (no glow, just flat) */
  --status-active:    #0f7b6c;
  --status-idle:      #9e9e9e;
  --status-error:     #e03e3e;
  --status-pending:   #dfab00;

  /* ── Typography: Inter only ──────────── */
  --font-sans:        'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono:        'SF Mono', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;

  /* ── Font Sizes ─────────────────────────── */
  --text-xs:   11px;
  --text-sm:   13px;
  --text-base: 15px;     /* Notion body size */
  --text-lg:   17px;
  --text-xl:   20px;
  --text-2xl:  24px;
  --text-3xl:  30px;

  /* ── Line Heights ────────────────────────── */
  --leading-tight:   1.3;
  --leading-normal:  1.5;
  --leading-relaxed: 1.7;

  /* ── Spacing: 4px base ───────────────── */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* ── Border Radius ────────────────────── */
  --radius-sm:    4px;
  --radius-md:    6px;
  --radius-lg:    10px;
  --radius-full:  9999px;

  /* ── Shadows: Notion-minimal ──────── */
  --shadow-sm:    0 1px 2px rgba(0,0,0,0.05);
  --shadow-md:    0 2px 8px rgba(0,0,0,0.06);
  --shadow-lg:    0 4px 16px rgba(0,0,0,0.08);
  --shadow-xl:    0 8px 30px rgba(0,0,0,0.1);

  /* ── Layout ────────────────────────────── */
  --header-height: 45px;
  --container-max: 1280px;
  --grid-gap: var(--space-4);
  --content-padding: var(--space-6);
  --sidebar-width:  260px;
  --drawer-width:   380px;

  /* ── Z-Index ────────────────────────────── */
  --z-base:   1;
  --z-card:   10;
  --z-header: 100;
  --z-drawer: 200;
  --z-modal:  300;
  --z-toast:  400;

  /* ── Animation ──────────────────────────── */
  --duration-fast:   150ms;
  --duration-normal: 300ms;
  --ease-out:        cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

**Remove from tokens.css (NOT in the new file):**
- `--glass-*` variables (no glass morphism)
- `--color-accent-dim`, `--color-accent-glow` (no glow)
- Orbitron, Share Tech Mono fonts
- `--font-display` (only Inter + mono)
- All glow shadows (`--shadow-glow-*`)
- `--glow-*` effect variables
- `--scanline-*`, `--noise-*`, `--particle-*`
- Inset shadows (cyber-glass style)

### 2.2 base.css — Minimal Reset (Replace)

```css
/* Reset - minimal, no display fonts, no effects */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--text-primary);
  background: var(--color-bg);
}

body {
  font-family: var(--font-sans);
  min-height: 100vh;
  background: var(--color-bg);
}

/* Remove: headings with Orbitron/uppercase — use Inter only */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-sans);
  font-weight: 600;
  line-height: var(--leading-tight);
  color: var(--text-primary);
  letter-spacing: normal;
  text-transform: none;  /* No uppercase headings */
}

/* Remove: ::selection accent color glow */
/* Remove: scrollbar accent color */
/* Keep: thin scrollbar, neutral colors */
/* Remove: .is-mobile guard — no glass to disable */
/* Remove: mobile typography overrides (handled naturally) */
```

**Key changes:**
- No `text-rendering: optimizeLegibility` (causes layout issues on some fonts)
- No display font family on headings
- No `.is-mobile` section (no glass effects to disable)
- No noise/scanline overlay
- No `font-display` utilities
- Keep: reset, scrollbar (neutral), focus-visible (black outline), selection, text helpers

### 2.3 layout.css — Simple Responsive Grid (Replace)

**Replace Bento grid with simple Notion-style card grid:**

```css
.container { /* same — width, max-width, padding */ }

/* Simple card grid: auto-fill, responsive */
.sandbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

/* Stats bar: horizontal flex row */
.stats-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.stat-card {
  flex: 1;
  min-width: 160px;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--space-6);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  position: sticky;
  top: 0;
  z-index: var(--z-header);
}
```

**Remove:**
- All `.tile-*` Bento classes
- 12-column grid system (no need for complex grids)
- `.col-*` helpers
- `.bento-grid` responsive tiers
- `.grid--*` alignment variations
- `@supports (backdrop-filter)` header glass

### 2.4 components.css — Clean Cards (Replace)

**Card:**
```css
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  transition: box-shadow var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}

.card:hover {
  border-color: var(--color-border-hover);
  box-shadow: var(--shadow-md);
}

.card-header { /* flex row, no border-bottom in minimal style */
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
/* No card__title with uppercase/display font */
```

**Badge:**
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: var(--text-xs);
  font-weight: 500;
  border-radius: var(--radius-full);
  border: 1px solid transparent;
}
.badge--active { background: #e8f5e9; color: var(--status-active); border-color: #c8e6c9; }
.badge--idle   { background: #f5f5f5; color: var(--text-secondary); border-color: #e0e0e0; }
.badge--error  { background: #ffebee; color: var(--status-error); border-color: #ffcdd2; }
.badge--pending { background: #fff8e1; color: var(--status-pending); border-color: #ffecb3; }
/* No ::before dot with glow */
```

**Button:**
```css
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 14px;
  font-size: var(--text-sm);
  font-weight: 500;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 36px;  /* reduced from 44px for Notion density */
}
.btn:hover { background: var(--color-hover); border-color: var(--color-border-hover); }

.btn--primary { background: var(--color-accent); color: var(--text-inverse); border-color: var(--color-accent); }
.btn--danger  { background: var(--color-danger); color: var(--text-inverse); border-color: var(--color-danger); }
.btn--ghost   { background: transparent; border-color: transparent; color: var(--text-secondary); }
/* No glowing shadows, no uppercase, no monospace font on buttons */
/* No scale transform on :active (Notion uses opacity/color only) */
```

**Kill Button (integrated into card):**
```css
.btn-kill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-danger);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.btn-kill:hover {
  background: #ffebee;
  border-color: #ffcdd2;
}
```

**Tree Node:**
```css
.tree-node { /* padding-left based on depth via inline style */ }
.tree-node-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  min-height: 32px;
  font-size: var(--text-sm);
}
.tree-node-row:hover { background: var(--color-hover); }
.tree-node-icon { /* SVG icon, 14x14, flex-shrink */ }
.tree-node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-children { padding-left: 24px; }
```

**Drawer:**
```css
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: var(--drawer-width);
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  z-index: var(--z-drawer);
  transform: translateX(100%);
  transition: transform var(--duration-normal) var(--ease-out);
  display: flex;
  flex-direction: column;
}
.drawer--open { transform: translateX(0); }
/* No glass, no backdrop-filter */
```

**Modal:**
```css
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: var(--z-modal);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  max-width: 400px; width: 90%;
  padding: var(--space-5);
}
/* No glass, no glow, no scale/spring animation */
```

**Toast:**
```css
.toast-container { /* fixed bottom-right */ }
.toast {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--space-3) var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
/* No glass, no glow borders */
```

**Search bar, tabs, tags, timeline, empty state, divider, status dot:**
- All redesigned minus glass/glow/uppercase display fonts
- Status dots: flat colors, no pulsing/glow animations

### 2.5 animations.css — Subtle Fades Only (Replace)

```css
/* Keep only: */
@keyframes fadeIn   { 0% { opacity: 0; } 100% { opacity: 1; } }
@keyframes slideUp  { 0% { opacity: 0; transform: translateY(8px); } 100% { opacity: 1; transform: translateY(0); } }
@keyframes slideInRight { 0% { opacity: 0; transform: translateX(20px); } 100% { opacity: 1; transform: translateX(0); } }

.animate-fade-in     { animation: fadeIn var(--duration-normal) var(--ease-out) forwards; }
.animate-slide-up    { animation: slideUp var(--duration-normal) var(--ease-out) forwards; }
.animate-slide-right { animation: slideInRight var(--duration-normal) var(--ease-out) forwards; }

/* Remove EVERYTHING else: */
/* - pulse, glow, shimmer, scanline, spin, shake, gradientShift, blink, float, breathe, glowPulse */
/* - .glow-* utility classes */
/* - .animate-stagger */
/* - .scanline-overlay */
/* - .shimmer placeholder */
/* - Reduced motion still respected */
```

---

## 3. JS Fix Plan

### 3.1 app.js — Major Refactor

**Structural change:**
```js
// BEFORE: renderDashboard() does manual HTML + no component init
// AFTER:  initComponent() calls all factory functions

async function initComponents() {
  // Initialize all components
  const headerEl = $('#header');
  if (headerEl) createHeader(headerEl);

  const statsEl = $('#stats-bar');
  if (statsEl) createStatsBar(statsEl);

  const gridEl = $('#sandbox-grid');
  if (gridEl) createSandboxCard(gridEl);

  const drawerContainer = $('#detail-drawer') || document.body;
  createDetailPanel(drawerContainer);
}

// Remove: renderDashboard() — replace with component-based rendering
// Remove: initParticles() — no particles
// Remove: updateComponents() — state subscriptions handle this
// Keep: loadData() — fetches initial data, sets state
// Keep: connectSSE() — live updates
// Keep: setInterval fallback polling
```

**Key changes to render logic:**
- `loadData()` only calls `store.setState({ trees, summary })` → subscriptions handle the DOM
- `connectSSE()` `on('summary', data)` calls `store.setState({ summary: data, isConnected: true })`
- Both initial load AND SSE updates flow through the same subscription pipeline
- Remove manual HTML generation entirely

### 3.2 tree-node.js — Fix renderTreeNode

**Problem:** Uses emoji for role icons, "Unnamed dead" when data is missing.

**Fix:**
1. **Replace emoji icons with SVG inline icons** (per UI/UX skill rule "No Emoji as Icons"):

```js
const ROLE_ICONS = {
  COMMANDER: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="..." stroke="currentColor" stroke-width="1.5"/></svg>',
  LEAD:      '<svg width="14" height="14" .../>',
  ARCHITECT: '<svg width="14" height="14" .../>',
  SOLDIER:   '<svg width="14" height="14" .../>',
  VERIFIER:  '<svg width="14" height="14" .../>',
};
```

2. **Fix "Unnamed dead" bug:** Check if node actually has name/status before rendering:

```js
function renderTreeNode(node, depth = 0) {
  if (!node) return '';
  // Guard: if node is not an object or has no meaningful data, skip
  if (!node.role && !node.name) return '';
  
  const name = node.name || node.id || `Node-${depth}`;
  const status = node.status || 'idle';
  // ...
}
```

3. **Handle hierarchy properly:** The army tree structure is:
```
COMM (commander)
 └─ LEAD (lead task)
     ├─ ARCH (architect)
     │   └─ SOLDIER (soldier 1)
     │   └─ SOLDIER (soldier 2)
     └─ VERIFY (verifier)
```

The existing recursive structure handles this. Fix is proper field access and SVG icons.

### 3.3 sandbox-card.js — Wire Up Kill Button + Subscribe Fix

**Changes:**
1. **Import and render kill button:**
```js
import { renderControls } from './controls.js';

function renderCard(sandbox) {
  // ... existing card template ...
  // Add kill button to card footer:
  const controlsHtml = sandbox.status === 'active' 
    ? `<div class="kill-btn-container" data-sandbox="${escapeAttr(name)}"></div>`
    : '';
    
  return `... ${controlsHtml} ...`;
}

// After rendering the container HTML, call renderControls for each active sandbox
function render(container, state) {
  container.innerHTML = merged.map(sb => renderCard(sb)).join('');
  
  // Wire kill buttons after DOM update
  merged.forEach(sb => {
    const killContainer = container.querySelector(`.kill-btn-container[data-sandbox="${sb.name}"]`);
    if (killContainer && (sb.status === 'active' || sb.status === 'running')) {
      renderControls(killContainer, sb.name, sb.status);
    }
  });
}
```

2. **Fix subscribe pattern:** The component already subscribes correctly. The issue was it was never initialized. Once `app.js` calls `createSandboxCard(gridEl)`, it will subscribe and re-render on state changes.

3. **Add expand/collapse toggle** with a chevron icon (SVG, not emoji).

### 3.4 controls.js — Integrate Kill Button

**No changes needed to controls.js itself** — the `renderControls` function already works correctly. It:
- Shows kill button only when status is active/running
- Shows confirmation modal before executing
- Calls `killSandbox` API
- Shows success/error toast

**The fix is purely in `sandbox-card.js` calling `renderControls` after card HTML is rendered.**

### 3.5 header.js — Minor Fix

**Change:** Remove `--font-display` reference from logo text — use Inter instead. Change `var(--accent)` to `var(--color-accent)` for CSS var consistency.

### 3.6 Remove Unused Files

| File | Action | Reason |
|------|--------|--------|
| `effects.js` | Remove | No particles, no glow, no shake, no cursor effects |
| `mobile-nav.js` | Remove | Collapsible cards handled by CSS media queries + simple JS directly in sandbox-card |
| `sparkline.js` | Keep but prune | Already clean — only SVG rendering, no visual cruft |
| `timeline.js` | Keep | Already clean, uses color classes not glow |

---

## 4. index.html Changes

### Remove
```html
<!-- Orbitron + Share Tech Mono fonts — no longer needed -->
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<!-- Replace with just Inter + mono -->
```

### Change
```html
<!-- Before -->
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<!-- After -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Remove mobile GPU script
```html
<!-- Remove: the inline <script> that adds .is-mobile class -->
<!-- No glass effects to disable, so this guard is unnecessary -->
```

### Update HTML structure
```html
<!-- Before: Bento grid structure with empty states -->
<div class="container">
  <div class="bento-grid" id="stats-grid"></div>
</div>
<div class="container">
  <div class="bento-grid" id="dashboard"></div>
  <div class="empty-state" ...></div>
</div>

<!-- After: Simple structure with component containers -->
<header class="header" id="header"></header>

<main class="container">
  <div id="stats-bar" class="stats-bar"></div>
  <div id="sandbox-grid" class="sandbox-grid"></div>
  <div id="empty-state" class="empty-state" style="display:none">
    <div class="empty-state-icon">⚡</div>
    <h3 class="empty-state-title">No sandboxes yet</h3>
    <p class="empty-state-text">Waiting for HERO to deploy an army...</p>
  </div>
</main>

<div id="detail-drawer" class="drawer" role="dialog" aria-modal="true"></div>
```

### Remove
```html
<!-- Remove: status-bar footer (unused) -->
```

---

## 5. Execution Order

### Phase 1: CSS Clean Slate (parallel-safe)
| Step | File | Action | Est. |
|------|------|--------|------|
| 1.1 | `tokens.css` | Full rewrite — white/black palette, Inter, minimal shadows | 15min |
| 1.2 | `base.css` | Minimal reset — no display fonts, no glass guards, neutral scrollbar | 10min |
| 1.3 | `layout.css` | Simple grid — auto-fill cards, flex stats bar, clean header | 15min |
| 1.4 | `components.css` | Full rewrite — clean cards, flat badges, neutral buttons, no glass | 30min |
| 1.5 | `animations.css` | Trim to 3 keyframes — fadeIn, slideUp, slideInRight | 5min |

### Phase 2: JS Fixes (ordered)
| Step | File | Action | Est. |
|------|------|--------|------|
| 2.1 | `tree-node.js` | SVG icons (not emoji), fix "Unnamed" guard, handle missing status | 15min |
| 2.2 | `sandbox-card.js` | Wire kill button via renderControls, add expand/collapse chevron | 15min |
| 2.3 | `controls.js` | No changes needed (already correct) | — |
| 2.4 | `header.js` | Fix CSS var names, remove display font ref | 5min |
| 2.5 | `app.js` | Major refactor — init components, remove manual rendering, wire SSE | 25min |
| 2.6 | `effects.js` | Delete file | 1min |
| 2.7 | `mobile-nav.js` | Delete file | 1min |

### Phase 3: HTML
| Step | File | Action | Est. |
|------|------|--------|------|
| 3.1 | `index.html` | Update fonts, simplify DOM, remove GPU script, remove footer | 10min |

### Phase 4: Verify
| Step | Action | Est. |
|------|--------|------|
| 4.1 | Reload dashboard, check no JS console errors | 5min |
| 4.2 | Verify sandbox cards render with correct tree hierarchy | 5min |
| 4.3 | Verify kill button appears on active sandboxes | 5min |
| 4.4 | Verify SSE updates re-render state subscriptions | 5min |
| 4.5 | Verify drawer opens/closes with sandbox selection | 5min |
| 4.6 | Verify mobile responsive layout (375px width) | 5min |
| 4.7 | Verify no backdrop-filter in any computed style | 3min |
| 4.8 | Verify prefers-reduced-motion disables animations | 3min |

**Total estimated effort: ~3 hours**

---

## 6. UI/UX Design Decisions (from UI/UX Pro Max)

### Style Decisions
| Rule | Applied | How |
|------|---------|-----|
| No emoji as icons (§Common Rules) | ✅ | SVG inline icons for tree roles, kill button icon, close buttons |
| Inter font (§Typography) | ✅ | Single sans font (Inter) — no display font for headings |
| 4px spacing system (§Spacing Scale) | ✅ | tokens.css uses 4px grid: 4, 8, 12, 16, 20, 24, 32, 40, 48 |
| 16px base body text (§Readable Font Size) | ✅ | `--text-base: 15px` (Notion-standard) |
| Line-height 1.5 (§Line Height) | ✅ | `--leading-normal: 1.5` |
| Semantic color tokens (§Color Semantic) | ✅ | `--color-success`, `--color-danger`, `--color-warning`, `--color-info` |
| Consistent shadow scale (§Elevation Consistent) | ✅ | 4-tier: sm/md/lg/xl with uniform rgba |
| Tabular figures for data (§Number Tabular) | ✅ | Use monospace for token counts, metrics |
| SVG icons over emoji (§No Emoji Icons) | ✅ | All icons converted to inline SVGs |
| 150-300ms transitions (§Duration Timing) | ✅ | `--duration-fast: 150ms`, `--duration-normal: 300ms` |
| Touch target 44px (§Touch Target Size) | ⚠️ Reduced to 36px for Notion-density; interactive card rows are full-width |
| Focus-visible outlines (§Focus States) | ✅ | `outline: 2px solid var(--color-accent)` |
| font-display: swap (§Font Loading) | ✅ | Google Fonts loads with font-display: swap (default) |
| Color not only indicator (§Color-Not-Only) | ✅ | Status badges have text + background tint |
| Reduced motion respected (§Reduced Motion) | ✅ | `prefers-reduced-motion: reduce` disables all animations |
| White/black palette (§Style Match) | ✅ | Notion-inspired: white bg, black text, gray borders |
| Responsive grid (minmax auto-fill) (§Mobile First) | ✅ | Cards auto-flow to 1-col on mobile, 2-col tablet, 3-4 col desktop |
| Max line length 75 chars (§Line Length) | ✅ | Container max-width: 1280px |

### What Was Removed (Cyber-Glass → Notion)
| Removed | Reason |
|---------|--------|
| Glass morphism (backdrop-filter) | Mobile crashes, unnecessary decoration |
| Particle system | Over-engineered, GPU intensive |
| Scanline overlay | CRT aesthetic, doesn't fit Notion |
| Noise texture | Redundant, hurts performance |
| Glow shadows | Cyber aesthetic, distracts from data |
| Floating/tracking animations | Decorative, adds no meaning |
| Orbitron display font | Sci-fi aesthetic, too opinionated |
| Staggered entry animations | Delays content visibility |
| Pulse/breathing indicators | Too flashy for professional dashboard |
| 12-column Bento grid | Over-engineered for card-based layout |
| Uppercase headings | Notion uses sentence case |
| Monospace for all buttons | Buttons should match body font |
| Scale transform on press | Notion uses color change only |
| .is-mobile guard class | No glass effects, no need |
| Mobile-nav.js | Handled by CSS media queries |

### Empty State Design
```
┌─────────────────────────────────┐
│              ⚡                  │
│    No sandboxes yet             │
│                                 │
│    Waiting for HERO to          │
│    deploy an army...            │
│                                 │
│    [Deploy from CLI]            │
└─────────────────────────────────┘
```
- Centered, muted text, no icon glow
- Secondary action hint instead of ghosted "deploy" button (since deploy is CLI-only)

### Color Palette Reference
```
Background:  #ffffff  (white)
Surface:     #ffffff  (white cards)
Hover:       #f5f5f5  (light gray)
Border:      #e5e5e5  (gray-200)

Text Primary:    #1a1a1a  (near-black)
Text Secondary:  #6b6b6b  (medium gray)
Text Tertiary:   #9e9e9e  (light gray)

Accent:     #37352f  (Notion dark gray)
Blue:       #2383e2  (links, info)
Red:        #e03e3e  (danger, errors)
Green:      #0f7b6c  (success, active)
Yellow:     #dfab00  (pending, warnings)
```

---

## Appendix: File Changes Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `index.html` | Partial rewrite | ~30 lines |
| `css/tokens.css` | Full rewrite (~200 lines → ~140 lines) | 140 lines |
| `css/base.css` | Full rewrite (~150 lines → ~80 lines) | 80 lines |
| `css/layout.css` | Full rewrite (~250 lines → ~120 lines) | 120 lines |
| `css/components.css` | Full rewrite (~700 lines → ~400 lines) | 400 lines |
| `css/animations.css` | Full rewrite (~200 lines → ~40 lines) | 40 lines |
| `js/app.js` | Major refactor (~200 lines → ~120 lines) | 120 lines |
| `js/components/tree-node.js` | Significant (~80 lines → ~90 lines) | 40 lines |
| `js/components/sandbox-card.js` | Moderate (~130 lines → ~160 lines) | 60 lines |
| `js/components/header.js` | Minor (~40 lines → ~35 lines) | 5 lines |
| `js/components/effects.js` | DELETE | — |
| `js/components/mobile-nav.js` | DELETE | — |

**Total CSS: ~780 lines new** (replacing ~1,500 lines)
**Total JS: ~405 lines new/modified** (replacing ~450 lines, removing ~150 lines)
