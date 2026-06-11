# SOLDIER BRIEF 3 — UI Components

## TASK
Build all UI components as ES modules with create/update/destroy lifecycle. Each component renders into a container element and subscribes to state changes.

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/js/components/header.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/stats-bar.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/sandbox-card.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/tree-node.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/detail-panel.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/timeline.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/sparkline.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/controls.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/toast.js`
- `/home/max/Development/HERO/src/hero/web/static/js/components/modal.js`

## COMPONENT LIFECYCLE PATTERN
Every component follows this contract:
```javascript
// header.js
import { subscribe, getState } from '../services/state.js';
import { escapeHtml, createElement } from '../utils/dom.js';

export function create(container) {
  // Render initial HTML into container
  // Subscribe to relevant state keys
  // Return { destroy() } for cleanup
  const unsub = subscribe('isConnected', () => update(container));
  update(container);
  return { destroy: unsub };
}

function update(container) {
  // Re-render based on current state
  const { isConnected } = getState();
  container.innerHTML = `...`;
}

// Or: export function render(container) { ... } for one-shot render
```

## SPEC

### header.js
- Logo: "HERO" in `var(--font-display)`, cyan accent, with ⚡ icon
- Live indicator: pulsing dot + "LIVE" text, red when disconnected
- Optional: time display, connection status
- Subscribe to: `isConnected`

### stats-bar.js
- Bento row of metric tiles (uses `.bento-grid` + `.tile-metric`)
- Tiles: Tokens Used (with budget %), Active Sandboxes (count), Tool Calls, Errors, Burn Rate
- Burn rate from state.burnRate (tokens/min)
- Token tile: show progress bar if budget > 0, color changes at 50%/80%
- Subscribe to: `summary`, `trees`, `errorCount`, `burnRate`

### sandbox-card.js
- Bento tile (`.tile-hero` for active, `.tile-metric` for idle)
- Header: sandbox name (font-display), status badge, model badge
- Body: tree view rendered by tree-node.js
- Footer: token usage mini-bar, tool call count
- Click: sets `selectedSandbox` in state → opens detail panel
- Expand/collapse: toggles `expanded[name]` in state
- Subscribe to: `trees`, `expanded`

### tree-node.js
- Recursive renderer for the army hierarchy tree
- Each node: role icon (⚡COMM, 🎯LEAD, 🏗️ARCH, 🤖SOLDIER, 🔍VERIFY), role name, status badge, model badge, task text
- Tree connectors: `├──` and `└──` characters in monospace
- Indentation: `--depth` CSS variable, 20px per level
- Colors: status-based — green (active), yellow (pending), red (error), blue (done), grey (idle)
- Export: `renderTreeNode(node, depth)` → HTML string
- Export: `renderTree(tree)` → HTML string (full tree from root)

### detail-panel.js
- Drawer sliding from right (`.drawer` class from CSS)
- Header: sandbox name, status badge, close button
- Sections:
  1. **Budget:** token used/total, progress bar, compactions, tool calls
  2. **Pipeline:** task name, created date, step statuses
  3. **Dispatch Tasks:** list with status indicators
  4. **Errors:** red-highlighted error messages
  5. **Git:** branch, commit (truncated), dirty status
  6. **Timeline:** rendered by timeline.js
- Fetches `/api/v1/sandbox/{name}` and `/api/v1/sandbox/{name}/timeline` on open
- Close on: backdrop click, Escape key, close button
- Subscribe to: `selectedSandbox`

### timeline.js
- Vertical timeline visualization
- Each event: colored dot (status-based), timestamp, role, event type, details
- Dot colors: green (running), cyan (done), red (error), yellow (pending)
- Time format: `HH:MM:SS`
- Export: `renderTimeline(events)` → HTML string

### sparkline.js
- SVG sparkline, no dependencies
- Input: array of numbers (token history)
- Render: SVG path with gradient fill underneath
- Size: 120×32px default, configurable
- Colors: `var(--color-accent)` stroke, gradient fill from accent to transparent
- Export: `renderSparkline(container, data, options?)` → void
- Re-renders on new data (efficient — only updates path d attribute)

### controls.js
- Action buttons for sandbox control
- Kill button: red, skull icon (☠️ or Lucide `skull`), triggers confirmation
- Flow: click Kill → modal.js confirmation → api.killSandbox() → toast success/error
- Confirmation requires typing sandbox name or clicking "Confirm" with delay
- Bearer token automatically included via auth.js
- Export: `renderControls(container, sandboxName)` → void
- Only shown for active/running sandboxes

### toast.js
- Notification system, bottom-right corner
- Types: success (green), error (red), info (cyan), warning (yellow)
- Auto-dismiss: 4s default, configurable
- Max 3 visible toasts, new ones push old ones out
- Animation: slide up + fade in, slide right + fade out on dismiss
- Export: `showToast(message, type?, duration?)` → void
- Export: `initToastContainer()` → void (creates the container div)

### modal.js
- Confirmation modal overlay
- Title, message, confirm button (danger-styled), cancel button
- Glass background with heavy blur
- Keyboard: Enter to confirm, Escape to cancel
- Focus trap: Tab cycles within modal
- Export: `showModal({ title, message, confirmText, onConfirm, onCancel? })` → void
- Export: `closeModal()` → void

## DESIGN
- **Colors:** Use CSS custom properties from tokens.css — never hardcode hex values
- **Typography:** `var(--font-display)` for headings/labels, `var(--font-mono)` for data/status, `var(--font-body)` for text
- **Spacing:** `var(--space-N)` tokens only
- **Borders:** `var(--glass-border)`, `var(--border-subtle)`
- **Glass:** Cards use `background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur))`
- **Status colors:** `var(--color-success)`, `var(--color-danger)`, `var(--color-warning)`, `var(--color-accent)`

## CONSTRAINTS
- ES modules — import from `../services/` and `../utils/`
- No innerHTML with unescaped user data — use escapeHtml/escapeAttr
- Each component is independently importable
- Subscribe to state in create(), unsubscribe in destroy()
- No direct DOM queries outside component container
- Sandbox names used as data attributes, always escaped

## ACCEPTANCE
1. All 10 component files created in `static/js/components/`
2. Each exports at least a `create(container)` function
3. tree-node.js recursively renders 3-level hierarchy (COMM→LEAD→ARCH→SOLDIER)
4. detail-panel.js fetches and displays sandbox data with 6 sections
5. sparkline.js renders SVG with gradient fill
6. toast.js shows/dismisses notifications with animation
7. modal.js traps focus and handles Enter/Escape
8. controls.js kill flow: button → modal → API call → toast
9. All components use CSS custom properties (no hardcoded colors)
