# ARCHITECT_BLUEPRINT — HERO Viewport v3 Cyber-Glass Overhaul

> **Generated:** 2026-05-27 by ARCH
> **Purpose:** Validate, refine, and set guardrails for the 4-wave, 7-soldier execution plan.

---

## 1. Final File Tree

```
src/hero/web/
├── server.py                         ← MODIFIED (add kill + spawn endpoints)
└── static/
    ├── index.html                    ← REWRITTEN (new shell, module imports)
    ├── css/
    │   ├── tokens.css                ← NEW (Soldier 1)
    │   ├── base.css                  ← NEW (Soldier 1)
    │   ├── layout.css                ← NEW (Soldier 1, modified by Soldier 5)
    │   ├── components.css            ← NEW (Soldier 1, modified by Soldier 5 + 6)
    │   └── animations.css            ← NEW (Soldier 1, modified by Soldier 6)
    ├── js/
    │   ├── app.js                    ← NEW (Soldier 7)
    │   ├── services/
    │   │   ├── api.js                ← NEW (Soldier 2)
    │   │   ├── sse.js                ← NEW (Soldier 2)
    │   │   ├── state.js              ← NEW (Soldier 2)
    │   │   └── auth.js               ← NEW (Soldier 2)
    │   ├── components/
    │   │   ├── header.js             ← NEW (Soldier 3)
    │   │   ├── stats-bar.js          ← NEW (Soldier 3)
    │   │   ├── sandbox-card.js       ← NEW (Soldier 3)
    │   │   ├── tree-node.js          ← NEW (Soldier 3)
    │   │   ├── detail-panel.js       ← NEW (Soldier 3)
    │   │   ├── timeline.js           ← NEW (Soldier 3)
    │   │   ├── sparkline.js          ← NEW (Soldier 3)
    │   │   ├── controls.js           ← NEW (Soldier 3, refined by Soldier 4)
    │   │   ├── toast.js              ← NEW (Soldier 3)
    │   │   ├── modal.js              ← NEW (Soldier 3, refined by Soldier 4)
    │   │   ├── effects.js            ← NEW (Soldier 6)
    │   │   └── mobile-nav.js         ← NEW (Soldier 5)
    │   └── utils/
    │       └── dom.js                ← NEW (Soldier 2)
    ├── app.js                        ← DELETED by Soldier 7 (old monolith, 635 lines)
    └── style.css                     ← DELETED by Soldier 7 (old stylesheet, 917 lines)
```

**Total new files:** 22 (5 CSS + 16 JS + 1 HTML rewrite)
**Files modified:** 1 (server.py — add endpoints)
**Files deleted:** 2 (old app.js, old style.css)

---

## 2. Data Flow

### 2.1 Primary Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HERO Backend                                │
│  server.py                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │ /api/v1/tree │  │ /api/v1/     │  │ /api/v1/events (SSE) │     │
│  │ /summary     │  │ sandbox/{n}  │  │   push every 2s      │     │
│  │ /bottlenecks │  │ /timeline    │  │                      │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘     │
└─────────┼─────────────────┼──────────────────────┼─────────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER (Soldier 2)                       │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ auth.js  │───▶│ api.js   │    │ sse.js   │    │ state.js │     │
│  │          │    │          │    │          │    │          │     │
│  │ token →  │    │ fetch →  │    │ EventSrc │    │ store    │     │
│  │ headers  │    │ JSON     │    │ → parse  │    │ subscribe│     │
│  └──────────┘    └────┬─────┘    └────┬─────┘    │ notify   │     │
│                       │               │          └────┬─────┘     │
│                       ▼               ▼               │           │
│                  ┌────────────────────────────────────┘           │
│                  │ setState({ trees, summary, ... })              │
│                  ▼                                                 │
│           ┌─────────────┐                                         │
│           │  state.js   │ ← Single source of truth               │
│           │  subscribers│                                         │
│           └──────┬──────┘                                         │
└──────────────────┼────────────────────────────────────────────────┘
                   │
          ┌────────┼────────┬────────┬────────┬────────┐
          ▼        ▼        ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPONENTS (Soldier 3)                           │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │ header   │ │ stats-bar│ │ sandbox- │ │ detail-  │ │ toast    ││
│  │          │ │          │ │ card     │ │ panel    │ │          ││
│  └──────────┘ └──────────┘ └────┬─────┘ └──────────┘ └──────────┘│
│                                 │                                   │
│                          ┌──────┴──────┐                           │
│                          ▼             ▼                           │
│                    ┌──────────┐  ┌──────────┐                     │
│                    │ tree-node│  │ controls │                     │
│                    │ sparkline│  │ modal    │                     │
│                    │ timeline │  │          │                     │
│                    └──────────┘  └──────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 SSE → State → Component Flow (Per Tick)

```
1. SSE 'summary' event arrives (every ~2s)
2. sse.js parses JSON → calls handlers.onSummary(data)
3. app.js onSummary:
   a. setState({ summary: data, isConnected: true })
   b. updateTokenHistory(data) → setState({ tokenHistory, burnRate })
   c. fetchTree() → setState({ trees: data.trees })
4. state.js notifies subscribers for changed keys:
   - 'trees' → sandbox-card.js re-renders cards
   - 'summary' → stats-bar.js re-renders metrics
   - 'burnRate' → stats-bar.js updates burn gauge
   - 'isConnected' → header.js updates live indicator
5. If tree unchanged (JSON compare), skip re-render (perf guard)
```

### 2.3 Kill Flow

```
User clicks ☠️ on sandbox card
  → controls.js: showModal({ title, message, onConfirm })
    → modal.js: renders glass overlay, focuses confirm button
    → User clicks "Kill {name}" or presses Enter
    → controls.js onConfirm:
      → api.killSandbox(name, name)  // confirmation_token = sandbox name
        → POST /api/v1/sandbox/{name}/kill
        → Body: { "confirmation_token": "{name}" }
        → Headers: { Authorization: "Bearer {token}" }
      → server.py: _check_auth → validate token → subprocess.run(["hero", "kill", name])
      → Response: { status: "killed", sandbox: name }
    → toast.js: showToast("Sandbox killed", "success")
    → Next SSE tick: sandbox disappears from tree
```

---

## 3. Component Dependency Graph

```
                    ┌─────────────┐
                    │  tokens.css │  (foundation — everything depends on this)
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ base.css │ │layout.css│ │          │
        └────┬─────┘ └────┬─────┘ │          │
             │            │       │components│
             │            │       │  .css    │
             │            │       │          │
             │            ▼       └────┬─────┘
             │    ┌──────────┐         │
             │    │animations│         │
             │    │  .css    │         │
             │    └────┬─────┘         │
             └─────────┴───────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │                 dom.js (util)                 │
    │           escapeHtml, createElement           │
    └──────────────────┬───────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ auth.js  │  │ state.js │  │          │
   └────┬─────┘  └────┬─────┘  │          │
        │              │        │          │
        ▼              ▼        │          │
   ┌──────────┐  ┌──────────┐  │          │
   │ api.js   │  │          │  │          │
   └────┬─────┘  │          │  │          │
        │        │          │  │          │
        ▼        │          │  │          │
   ┌──────────┐  │          │  │          │
   │ sse.js   │  │          │  │          │
   └──────────┘  │          │  │          │
                 │          │  │          │
    ┌────────────┴──────────┴──┴──────────┘
    │         COMPONENTS
    ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ header   │ │stats-bar │ │sandbox-  │ │tree-node │
│          │ │          │ │card      │ │sparkline │
│ depends: │ │ depends: │ │ depends: │ │timeline  │
│ state    │ │ state    │ │ state    │ │          │
│ dom      │ │ dom      │ │ dom      │ │ depends: │
│ sse(ref) │ │ sparkline│ │ tree-node│ │ (none)   │
└──────────┘ └──────────┘ │ controls │ └──────────┘
                          │ toast    │
┌──────────┐ ┌──────────┐ └──────────┘
│detail-   │ │ controls │
│panel     │ │ modal    │
│          │ │          │
│ depends: │ │ depends: │
│ state    │ │ state    │
│ api      │ │ api      │
│ timeline │ │ toast    │
│ toast    │ │ dom      │
└──────────┘ └──────────┘

┌──────────┐ ┌──────────┐
│ toast    │ │ modal    │
│          │ │          │
│ depends: │ │ depends: │
│ dom      │ │ dom      │
└──────────┘ └──────────┘

┌──────────┐ ┌──────────┐
│ effects  │ │mobile-nav│
│          │ │          │
│ depends: │ │ depends: │
│ (none)   │ │ (none)   │
└──────────┘ └──────────┘
```

### Module Import Rules

| From | May Import |
|------|-----------|
| `js/app.js` | Everything (entry point) |
| `js/components/*` | `../services/*`, `../utils/dom.js`, sibling components |
| `js/services/*` | Sibling services only (no components, no utils except dom) |
| `js/utils/*` | Nothing (leaf modules) |
| `css/*` | Only `tokens.css` via custom properties (implicit) |

**Forbidden:** Components importing other components that import them back (no circular deps).

---

## 4. Security Architecture

### 4.1 Auth Flow

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ sessionStorage│──▶│   auth.js    │──▶│  api.js     │
│ hero_web_token│   │ getAuthHeaders│   │ fetch()     │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  server.py  │
                                       │ _check_auth │
                                       │ Bearer check│
                                       └─────────────┘
```

### 4.2 Kill Endpoint Security Analysis

**Threat Model:**

| Threat | Mitigation | Status |
|--------|-----------|--------|
| Unauthorized kill | Bearer token required (`_check_auth`) | ✅ Adequate |
| Accidental kill | `confirmation_token` must match sandbox name | ✅ Adequate |
| CSRF | Bearer token in header (not cookie) → immune to CSRF | ✅ Immune |
| Replay attack | Token is session-scoped (sessionStorage) + HTTPS recommended | ⚠️ Weak |
| Token leakage | sessionStorage (cleared on tab close), not localStorage | ✅ Acceptable |
| Sandbox enumeration | `/api/v1/tree` returns all sandbox names (auth required) | ⚠️ Info leak |
| Denial of service | No rate limiting on kill endpoint | ⚠️ Risk |

**ARCH Assessment: The kill endpoint is adequately secure for a local/internal dashboard.** The confirmation token (sandbox name as proof-of-intent) is a simple but effective pattern. For production exposure, add rate limiting.

### 4.3 XSS Prevention

- `dom.js` provides `escapeHtml()` and `escapeAttr()` — **mandatory** for all user/sandbox data
- No `innerHTML` with unescaped data — components must use `createElement()` or escaped templates
- CSP: Not explicitly set — recommend adding `Content-Security-Policy` header in future

### 4.4 Recommendations (Non-blocking)

1. **Add rate limiting** to kill endpoint (e.g., 5/min per IP)
2. **Add CSP header** to server.py: `script-src 'self' https://fonts.googleapis.com`
3. **HTTPS required** for any external exposure (Tailscale Funnel handles this)

---

## 5. Risk Register

### RISK 1: File Contention Between Parallel Soldiers (Wave 1, 3, 4)

**Severity:** HIGH
**Probability:** MEDIUM

**Description:** Soldier 5 (Mobile) modifies `layout.css` and `components.css` which were created by Soldier 1 (Design System). Soldier 6 (Polish) modifies `components.css`, `animations.css`, and `tokens.css`. Soldier 4 (Controls) modifies `server.py`. If parallel soldiers write to the same file, last-write-wins data loss occurs.

**Mitigation:**
- Wave 3: Soldier 4 writes `server.py` (Python). Soldier 6 writes CSS/JS files. **No overlap.** ✅
- Wave 4: Soldier 5 modifies CSS. Soldier 7 writes `index.html` + `js/app.js`. **No overlap.** ✅
- Wave 3→4 chain: Soldier 6 creates CSS before Soldier 5 modifies it. **Sequential dependency respected.** ✅
- **Soldier briefs explicitly list which files each soldier creates vs. modifies.** The brief assignments are clean — no two soldiers modify the same file.

**Verdict:** Low risk. The wave structure is sound.

---

### RISK 2: SSE Reconnect Race Condition

**Severity:** MEDIUM
**Probability:** MEDIUM

**Description:** When the browser backgrounds the tab, EventSource may be throttled. On re-focus, multiple reconnect attempts could fire simultaneously, creating duplicate connections.

**Mitigation:**
- `sse.js` must implement singleton pattern — only one active EventSource at a time
- `disconnect()` must be called before `connect()` creates new instance
- Soldier 2 brief specifies exponential backoff (1s → 2s → 4s → 8s → 30s max)
- `app.js` creates SSE once in `init()`, not in a loop

**Action for Soldier 2:** Ensure `createSSE()` guards against double-connect. Add `let activeEventSource = null` at module scope; close existing before creating new.

---

### RISK 3: Chart.js CDN Dependency Breaks Offline/No-Internet

**Severity:** LOW
**Probability:** LOW

**Description:** The plan mentions Chart.js v4 from CDN, but the briefs don't actually use Chart.js in any component. The sparkline is pure SVG. This is a non-issue.

**Mitigation:** Remove Chart.js references from any documentation. The sparkline.js component uses pure SVG — no external dependency needed. **Clean.**

---

### RISK 4: Font Loading Causes Layout Shift (FOUT/FOIT)

**Severity:** MEDIUM
**Probability:** HIGH

**Description:** Google Fonts (Orbitron, Share Tech Mono, Inter) load asynchronously. Until loaded, text renders in fallback font, causing layout shift. Orbitron is particularly wide — fallback sans-serif will reflow headings.

**Mitigation:**
- Use `display=swap` (specified in soldier briefs) — prevents FOIT, allows FOUT
- Font preconnect hints (`fonts.googleapis.com`, `fonts.gstatic.com`) reduce latency
- Orbitron is only used for headings/labels (small text volume) — shift is minimal
- Share Tech Mono for data has similar metrics to system monospace — minimal shift

**Action for Soldier 7:** Include `<link rel="preconnect">` in `<head>` before font stylesheet link.

---

### RISK 5: Large Sandbox Trees Cause Render Jank

**Severity:** MEDIUM
**Probability:** LOW

**Description:** If a sandbox has many dispatch entries (50+), the recursive tree renderer could produce large DOM trees. On each SSE tick (2s), `innerHTML` replacement could cause visible jank.

**Mitigation:
- `tree-node.js` returns HTML strings (not DOM manipulation) — fast
- `app.js` includes JSON equality check: `if (!treesEqual(data.trees, lastTrees))` — skips re-render if unchanged
- Detail panel fetches data on-demand (not on every tick)
- If needed: virtual scrolling can be added later (not in scope)

**Action for Soldier 3:** Ensure `sandbox-card.js` compares tree JSON before re-rendering inner content. Only replace `innerHTML` if data actually changed.

---

### RISK 6: Subprocess Kill Fails Silently or Hangs

**Severity:** MEDIUM
**Probability:** LOW

**Description:** `subprocess.run(["hero", "kill", name], timeout=30)` could hang if `hero kill` doesn't respond, or fail if `hero` isn't in PATH.

**Mitigation:**
- 30-second timeout specified in Soldier 4 brief ✅
- `FileNotFoundError` caught for missing CLI ✅
- Server logs warning on failure ✅
- Frontend shows toast error, not silent failure ✅

**Action for Soldier 4:** Log both stdout and stderr on failure for debugging.

---

### RISK 7: Backdrop-filter Not Supported in All Browsers

**Severity:** LOW
**Probability:** LOW

**Description:** `backdrop-filter: blur()` is not supported in Firefox without flag (as of 2026, it is supported). Fallback: solid background color.

**Mitigation:**
- Soldier 6 brief specifies `-webkit-backdrop-filter` prefix ✅
- Glass components have solid `background` as fallback ✅
- `var(--glass-bg)` is semi-transparent — works without blur

**Action for Soldier 6:** Ensure every `backdrop-filter` rule has a solid background fallback before it.

---

## 6. Soldier Quality Standards

### 6.1 Code Style

```javascript
// ✅ GOOD — Module header
/* HERO Viewport — [module name] */

// ✅ GOOD — Named exports
export function create(container) { ... }
export function renderTree(tree) { ... }

// ❌ BAD — Default exports (harder to tree-shake, less explicit)
export default { create, renderTree }

// ✅ GOOD — Const for non-reassigned values
const MAX_TOASTS = 3;

// ✅ GOOD — Arrow functions for callbacks
subscribe('trees', (val) => update(container));

// ❌ BAD — var
var x = 1;
```

### 6.2 Module Pattern

Every component module follows this contract:

```javascript
/* HERO Viewport — [Component Name] */
import { subscribe, getState } from '../services/state.js';
import { escapeHtml } from '../utils/dom.js';

/**
 * Create and mount the component.
 * @param {HTMLElement} container - DOM element to render into
 * @returns {{ destroy: () => void }} Cleanup function
 */
export function create(container) {
  const unsub = subscribe('[key]', () => update(container));
  update(container);
  return { destroy: unsub };
}

function update(container) {
  const state = getState();
  // Re-render — use escapeHtml on ALL dynamic content
  container.innerHTML = `...`;
}
```

### 6.3 XSS Rules

| Data | Method | Example |
|------|--------|---------|
| Sandbox name in text | `escapeHtml()` | `` `${escapeHtml(name)}` `` |
| Sandbox name in attribute | `escapeAttr()` | `` data-name="${escapeAttr(name)}" `` |
| Status string | `escapeHtml()` | Status values from API |
| Model name | `escapeHtml()` | Model strings from API |
| Task description | `escapeHtml()` | Free-text from dispatch files |

**Rule: If it comes from the API, it gets escaped. No exceptions.**

### 6.4 CSS Rules

```css
/* ✅ GOOD — Use tokens */
.card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
}

/* ❌ BAD — Hardcoded values */
.card {
  background: rgba(14, 14, 24, 0.75);
  border: 1px solid rgba(0, 240, 255, 0.08);
  padding: 16px;
  border-radius: 14px;
}
```

**Rule: All colors, spacing, radii, shadows, and fonts reference `var(--*)` tokens. If a token doesn't exist, add it to `tokens.css` first.**

### 6.5 Error Handling

```javascript
// ✅ GOOD — Catch, log, show user
try {
  const data = await fetchTree();
  setState({ trees: data.trees || [] });
} catch (err) {
  console.error('Failed to load tree:', err);
  showToast('Failed to load data', 'error');
}

// ❌ BAD — Silent swallow
try {
  const data = await fetchTree();
} catch (e) {}

// ❌ BAD — No try/catch on API calls
const data = await fetchTree();
```

### 6.6 File Header Template

Every new file must begin with:

```javascript
/* HERO Viewport — [Module Name] */
```

or

```css
/* HERO Viewport — [filename] */
```

---

## 7. Contingency Plans

### 7.1 If a Soldier Fails to Create All Assigned Files

**Detection:** After each wave, verify file existence:
```bash
# After Wave 1
ls -la src/hero/web/static/css/
ls -la src/hero/web/static/js/services/
ls -la src/hero/web/static/js/utils/

# After Wave 2
ls -la src/hero/web/static/js/components/

# After Wave 3
grep -c "kill" src/hero/web/server.py
ls -la src/hero/web/static/js/components/effects.js

# After Wave 4
ls -la src/hero/web/static/js/components/mobile-nav.js
head -5 src/hero/web/static/index.html  # Should show new template
```

**Recovery:** Spawn a cleanup soldier with the missing file specs. The briefs are detailed enough to extract exact requirements.

### 7.2 If CSS Tokens Conflict Between Soldiers

**Scenario:** Soldier 6 adds tokens that clash with Soldier 1's names.

**Mitigation:**
- Soldier 1 defines the base token set (40+ properties)
- Soldier 6 brief only adds *new* tokens (glow, scanline, noise, particle)
- Soldier 6 brief explicitly says "Add Effect Tokens" — not rename existing ones
- Token naming convention: `--{category}-{variant}` (e.g., `--glow-accent`, `--scanline-opacity`)

**Recovery:** If conflict found, Soldier 6 tokens take precedence (they're additive/override). Merge by keeping Soldier 1's base values and Soldier 6's additions.

### 7.3 If server.py Kill Endpoint Breaks Existing Routes

**Mitigation:**
- New endpoints are *additions* — they don't modify existing route functions
- Existing routes (`/api/v1/tree`, `/summary`, etc.) are untouched
- `_check_auth()` function is not modified

**Verification after Soldier 4:**
```bash
# Start server
python -m hero.web.server &
# Test existing endpoints still work
curl -s http://localhost:8765/api/v1/tree | head -c 100
curl -s http://localhost:8765/api/v1/summary | head -c 100
# Test new endpoint exists (should return 401 without token)
curl -s -X POST http://localhost:8765/api/v1/sandbox/test/kill
```

### 7.4 If Integration (Soldier 7) Produces a Broken index.html

**Mitigation:**
- The `_DASHBOARD_HTML` fallback in `server.py` is preserved
- If `static/index.html` is broken, `server.py` serves the embedded fallback
- Manual recovery: delete broken `index.html`, server auto-falls back

**Verification:** After Soldier 7, open browser → check console for errors → verify dashboard renders.

---

## 8. Pre-flight Checklist

### Before Wave 1 (Soldiers 1 + 2)

- [ ] `src/hero/web/static/css/` directory exists (create if not)
- [ ] `src/hero/web/static/js/services/` directory exists (create if not)
- [ ] `src/hero/web/static/js/utils/` directory exists (create if not)
- [ ] `src/hero/web/static/js/components/` directory exists (create if not)
- [ ] Existing `server.py` is unmodified (git status clean)
- [ ] Existing `app.js` and `style.css` still present (not deleted yet)

```bash
mkdir -p src/hero/web/static/{css,js/services,js/components,js/utils}
```

### Before Wave 2 (Soldier 3)

- [ ] All 5 CSS files exist in `css/` (Soldier 1 complete)
- [ ] All 5 JS files exist in `js/services/` and `js/utils/` (Soldier 2 complete)
- [ ] `tokens.css` exports ≥40 custom properties
- [ ] `state.js` exports `subscribe`, `getState`, `setState`
- [ ] `dom.js` exports `escapeHtml`, `createElement`

```bash
# Verify Wave 1 completion
test -f src/hero/web/static/css/tokens.css && echo "✅ tokens.css"
test -f src/hero/web/static/css/base.css && echo "✅ base.css"
test -f src/hero/web/static/css/layout.css && echo "✅ layout.css"
test -f src/hero/web/static/css/components.css && echo "✅ components.css"
test -f src/hero/web/static/css/animations.css && echo "✅ animations.css"
test -f src/hero/web/static/js/services/api.js && echo "✅ api.js"
test -f src/hero/web/static/js/services/sse.js && echo "✅ sse.js"
test -f src/hero/web/static/js/services/state.js && echo "✅ state.js"
test -f src/hero/web/static/js/services/auth.js && echo "✅ auth.js"
test -f src/hero/web/static/js/utils/dom.js && echo "✅ dom.js"
```

### Before Wave 3 (Soldiers 4 + 6)

- [ ] All 10 component files exist in `js/components/` (Soldier 3 complete)
- [ ] Each component exports `create(container)` function
- [ ] `controls.js` and `modal.js` exist (Soldier 4 will refine them)
- [ ] `server.py` is accessible for modification (no locks)

```bash
# Verify Wave 2 completion
for f in header stats-bar sandbox-card tree-node detail-panel timeline sparkline controls toast modal; do
  test -f "src/hero/web/static/js/components/${f}.js" && echo "✅ ${f}.js" || echo "❌ ${f}.js MISSING"
done
```

### Before Wave 4 (Soldiers 5 + 7)

- [ ] `server.py` has kill endpoint (Soldier 4 complete)
- [ ] `effects.js` exists (Soldier 6 complete)
- [ ] All CSS files have glassmorphism applied (Soldier 6 complete)
- [ ] Old `app.js` and `style.css` still present (Soldier 7 will delete them)

```bash
# Verify Wave 3 completion
grep -q "api_kill_sandbox" src/hero/web/server.py && echo "✅ kill endpoint"
test -f src/hero/web/static/js/components/effects.js && echo "✅ effects.js"
```

### Final Verification (After All Waves)

```bash
# 1. File count
echo "New files:"
find src/hero/web/static/ -name "*.js" -o -name "*.css" | wc -l

# 2. Old files deleted
test ! -f src/hero/web/static/app.js && echo "✅ old app.js deleted" || echo "❌ old app.js still exists"
test ! -f src/hero/web/static/style.css && echo "✅ old style.css deleted" || echo "❌ old style.css still exists"

# 3. Server starts
timeout 5 python -c "from hero.web.server import app; print('✅ server imports cleanly')" 2>&1

# 4. No syntax errors in JS modules
for f in $(find src/hero/web/static/js -name "*.js"); do
  node --check "$f" 2>&1 && echo "✅ $f" || echo "❌ $f"
done

# 5. CSS custom properties count
grep -c "var(--" src/hero/web/static/css/components.css
```

---

## 9. Architect Notes

### What's Sound About This Plan

1. **Clean wave dependencies.** Wave 1 (foundation) → Wave 2 (components) → Wave 3 (features + polish) → Wave 4 (mobile + integration). No back-dependencies.
2. **No file contention.** Verified: no two soldiers in the same wave write to the same file.
3. **Vanilla JS is the right call.** No framework overhead, no build step complexity, ES modules are native. The dashboard is simple enough.
4. **The fallback is preserved.** `_DASHBOARD_HTML` in server.py ensures the server always has something to serve, even if the new frontend is broken.

### What Could Be Better

1. **Soldier 7 is too big.** Rewriting `index.html`, creating `js/app.js`, deleting old files, and wiring everything is integration-heavy. If this soldier fails, the entire overhaul is invisible. Consider splitting into 7a (index.html + app.js) and 7b (cleanup).
2. **No automated tests.** The verification strategy is manual (open browser, check). A basic smoke test script would catch regressions.
3. **No versioning.** If we need to rollback, we're relying on git. Make sure to commit after each wave.

### Final Guardrail

**If at any point a soldier's output doesn't compile/parse, DO NOT proceed to the next wave.** Fix forward or re-spawn the failed soldier. The wave dependency chain is strict — broken foundation = broken everything above it.

---

*Blueprint complete. Execute with precision.*
