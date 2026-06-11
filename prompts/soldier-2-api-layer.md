# SOLDIER BRIEF 2 — API Layer (Services + Utils)

## TASK
Create the modular JavaScript service layer: API client, SSE manager, reactive state store, auth manager, and DOM utilities.

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/js/services/api.js`
- `/home/max/Development/HERO/src/hero/web/static/js/services/sse.js`
- `/home/max/Development/HERO/src/hero/web/static/js/services/state.js`
- `/home/max/Development/HERO/src/hero/web/static/js/services/auth.js`
- `/home/max/Development/HERO/src/hero/web/static/js/utils/dom.js`

## SPEC

### auth.js — Token Management
```javascript
// Exports:
//   getToken() → string|null
//   setToken(token) → void
//   clearToken() → void
//   getAuthHeaders() → { Authorization?: string }
//   isAuthenticated() → boolean

// Behavior:
// - Reads/writes sessionStorage key 'hero_web_token'
// - getAuthHeaders() returns { Authorization: 'Bearer <token>' } or {}
// - If HERO_WEB_TOKEN is not set server-side, auth is open (no header needed)
// - Prompt user for token on 401 response (via exported onUnauthorized callback)
```

### api.js — Fetch Wrappers
```javascript
// Exports:
//   fetchTree() → Promise<{ trees: Array }>
//   fetchSummary() → Promise<SummaryData>
//   fetchSandbox(name) → Promise<SandboxDetail>
//   fetchTimeline(name) → Promise<TimelineEvent[]>
//   fetchBottlenecks() → Promise<Bottleneck[]>
//   killSandbox(name, confirmationToken) → Promise<{ status: string }>
//
// Each function:
// 1. Calls getAuthHeaders() from auth.js
// 2. Fetches the endpoint with proper headers
// 3. On 401: calls auth.onUnauthorized(), throws
// 4. On non-ok: throws with status + message
// 5. Returns parsed JSON
//
// killSandbox sends POST to /api/v1/sandbox/{name}/kill
// with body { confirmation_token: string }
```

### sse.js — EventSource Manager
```javascript
// Exports:
//   createSSE(url, handlers) → { connect(), disconnect(), isConnected() }
//
// Parameters:
//   url: string — SSE endpoint URL
//   handlers: {
//     onSummary: (data) => void,
//     onError: (error) => void,
//     onConnect: () => void,
//     onDisconnect: () => void
//   }
//
// Behavior:
// - Creates EventSource to /api/v1/events
// - Listens for 'summary' events, parses JSON, calls onSummary
// - Listens for 'error' events, calls onError
// - Auto-reconnect on connection error with exponential backoff:
//   1s → 2s → 4s → 8s → max 30s
// - Resets backoff on successful message
// - isConnected() returns current connection state
// - disconnect() closes EventSource cleanly
// - Adds auth token as query param ?token=xxx if set
```

### state.js — Reactive State Store
```javascript
// Exports:
//   store — the state object
//   subscribe(key, callback) → unsubscribe function
//   getState() → current state snapshot
//   setState(partial) → void (merges + notifies subscribers)
//
// Initial state shape:
// {
//   trees: [],
//   summary: null,
//   sandboxes: {},
//   tokenHistory: [],      // last 30 token counts for sparkline
//   bottlenecks: [],
//   expanded: {},          // { sandboxName: boolean }
//   searchQuery: '',
//   statusFilter: '',
//   errorCount: 0,
//   isConnected: false,
//   selectedSandbox: null, // for detail panel
//   burnRate: 0,           // tokens/min
// }
//
// subscribe('trees', callback) — callback receives (newValue, key)
// setState({ trees: newData }) — merges, triggers all 'trees' subscribers
// Computed: burnRate auto-calculated from tokenHistory on update
```

### dom.js — DOM Utilities
```javascript
// Exports:
//   escapeHtml(str) → string       // XSS-safe text insertion
//   escapeAttr(str) → string       // XSS-safe attribute insertion
//   createElement(tag, attrs, children) → HTMLElement
//   qs(selector, parent?) → Element | null
//   qsa(selector, parent?) → Element[]
//   on(el, event, handler, options?) → void
//   delegate(parent, selector, event, handler) → void  // event delegation
//   html(strings, ...values) → string  // tagged template with auto-escape
//
// createElement example:
//   createElement('div', { class: 'card', onclick: handler }, [
//     createElement('span', {}, ['Hello'])
//   ])
//
// html tagged template:
//   html`<div class="${cls}">${unsafeText}</div>` — auto-escapes interpolations
```

## DESIGN
- All modules use ES module syntax (`export`/`import`)
- No global state — everything through state.js store
- Auth token flows: sessionStorage → api.js headers → server Bearer check
- SSE reconnect: exponential backoff, max 30s, reset on success
- DOM utils: defensive against null/undefined, always escape user content

## CONSTRAINTS
- Pure vanilla JS, ES modules (export/import)
- No dependencies, no CDN
- All API calls go through api.js (centralized error handling)
- Auth state in sessionStorage only (not localStorage)
- SSE must survive page backgrounding (browser may throttle EventSource)
- Each file is self-contained — import only from sibling modules

## ACCEPTANCE
1. All 5 files created in correct paths under `static/js/`
2. Each file has header comment: `/* HERO Viewport — [module name] */`
3. `api.js` exports functions for all 6 endpoints (tree, summary, sandbox, timeline, bottlenecks, kill)
4. `sse.js` creates reconnecting EventSource with exponential backoff
5. `state.js` implements subscribe/notify pattern with ≥10 state keys
6. `auth.js` manages sessionStorage token, returns headers object
7. `dom.js` exports escapeHtml, createElement, and html tagged template
8. All files use `export` syntax — ready for `<script type="module">` import
