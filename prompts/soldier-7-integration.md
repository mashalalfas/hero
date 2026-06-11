# SOLDIER BRIEF 7 — Integration (app.js + index.html Rewrite)

## TASK
Rewrite `index.html` and create new `js/app.js` entry point to wire all modules together. Delete old monolithic files.

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/js/app.js` — New entry point

## FILES TO REWRITE
- `/home/max/Development/HERO/src/hero/web/static/index.html` — New shell

## FILES TO DELETE
- `/home/max/Development/HERO/src/hero/web/static/app.js` — Old monolith (replaced by js/app.js)
- `/home/max/Development/HERO/src/hero/web/static/style.css` — Old stylesheet (replaced by css/)

## SPEC

### index.html — New Shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>HERO Viewport</title>

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <!-- CSS (order matters: tokens first, then base, layout, components, animations) -->
  <link rel="stylesheet" href="/static/css/tokens.css">
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/layout.css">
  <link rel="stylesheet" href="/static/css/components.css">
  <link rel="stylesheet" href="/static/css/animations.css">

  <meta name="theme-color" content="#0a0a0f">
</head>
<body class="scanline-overlay">

  <!-- Header -->
  <header class="header" id="header"></header>

  <!-- Stats Bar (bento row) -->
  <div class="container">
    <div class="bento-grid" id="stats-grid"></div>
  </div>

  <!-- Search -->
  <div class="container">
    <div class="search-bar" id="search-bar"></div>
  </div>

  <!-- Main Dashboard (sandbox cards in bento grid) -->
  <main class="container">
    <div class="bento-grid" id="dashboard"></div>
    <div class="empty-state" id="empty-state" style="display:none">
      <div class="empty-icon">📭</div>
      <div class="empty-message">No sandboxes yet</div>
      <div class="empty-hint">Waiting for HERO to deploy…</div>
    </div>
  </main>

  <!-- Status Bar -->
  <footer class="status-bar" id="status-bar"></footer>

  <!-- Detail Drawer -->
  <aside class="drawer" id="detail-drawer">
    <div class="drawer-backdrop"></div>
    <div class="drawer-panel" id="drawer-panel">
      <div class="drawer-header">
        <h2 id="drawer-name"></h2>
        <span class="drawer-status" id="drawer-status"></span>
        <button class="drawer-close" id="drawer-close">✕</button>
      </div>
      <div class="drawer-body" id="drawer-body"></div>
    </div>
  </aside>

  <!-- Toast Container -->
  <div id="toast-container"></div>

  <!-- Modal Container -->
  <div id="modal-container"></div>

  <!-- App Entry (ES module) -->
  <script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

### js/app.js — Entry Point

```javascript
/* HERO Viewport — App Entry Point */

// ── Services ──
import { getState, setState, subscribe } from './services/state.js';
import { fetchTree, fetchSummary, fetchBottlenecks } from './services/api.js';
import { createSSE } from './services/sse.js';
import { getToken, setToken, getAuthHeaders } from './services/auth.js';

// ── Components ──
import { create as createHeader } from './components/header.js';
import { create as createStatsBar } from './components/stats-bar.js';
import { renderTree } from './components/tree-node.js';
import { create as createDetailPanel } from './components/detail-panel.js';
import { renderSparkline } from './components/sparkline.js';
import { initToastContainer } from './components/toast.js';
import { initParticles } from './components/effects.js';

// ── Utils ──
import { escapeHtml, qs, on, delegate } from './utils/dom.js';

// ── Init ──
async function init() {
  // Prompt for token if needed
  promptForToken();

  // Initialize toast system
  initToastContainer();

  // Mount components
  const headerEl = qs('#header');
  const statsEl = qs('#stats-grid');
  const dashboardEl = qs('#dashboard');
  const emptyEl = qs('#empty-state');

  if (headerEl) createHeader(headerEl);
  if (statsEl) createStatsBar(statsEl);

  // Detail panel
  createDetailPanel(qs('#detail-drawer'));

  // Particles (background effect)
  initParticles(document.body);

  // Initial data load
  await Promise.allSettled([
    loadTree(),
    loadSummary(),
    loadBottlenecks(),
  ]);

  // Connect SSE for live updates
  const sse = createSSE('/api/v1/events', {
    onSummary: (data) => {
      setState({ summary: data, isConnected: true });
      updateTokenHistory(data);
      loadTree(); // Refresh tree on summary update
    },
    onError: (err) => {
      console.warn('SSE error:', err);
      setState({ isConnected: false });
    },
    onConnect: () => setState({ isConnected: true }),
    onDisconnect: () => setState({ isConnected: false }),
  });

  // Subscribe to state changes → re-render
  subscribe('trees', () => renderDashboard(dashboardEl, emptyEl));
  subscribe('expanded', () => renderDashboard(dashboardEl, emptyEl));
  subscribe('searchQuery', () => renderDashboard(dashboardEl, emptyEl));
  subscribe('statusFilter', () => renderDashboard(dashboardEl, emptyEl));

  // Search bar setup
  setupSearch();

  // Periodic tree refresh (backup for SSE)
  setInterval(loadTree, 15000);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      setState({ selectedSandbox: null });
    }
    // Ctrl+K or / to focus search
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !e.target.matches('input'))) {
      e.preventDefault();
      qs('#search-input')?.focus();
    }
  });

  console.log('%c⚡ HERO Viewport v3 — Cyber-Glass', 'color: #00f0ff; font-size: 14px; font-weight: bold;');
}

// ── Data Loading ──
async function loadTree() {
  try {
    const data = await fetchTree();
    setState({ trees: data.trees || [] });
  } catch (err) {
    console.error('Failed to load tree:', err);
  }
}

async function loadSummary() {
  try {
    const data = await fetchSummary();
    setState({ summary: data });
    updateTokenHistory(data);
  } catch (err) {
    console.error('Failed to load summary:', err);
  }
}

async function loadBottlenecks() {
  try {
    const data = await fetchBottlenecks();
    setState({ bottlenecks: data });
  } catch (err) {
    console.error('Failed to load bottlenecks:', err);
  }
}

function updateTokenHistory(summary) {
  const { tokenHistory } = getState();
  const newHistory = [...tokenHistory, summary.total_tokens_used || 0].slice(-30);
  const burnRate = calcBurnRate(newHistory);
  setState({ tokenHistory: newHistory, burnRate });
}

function calcBurnRate(history) {
  if (history.length < 2) return 0;
  const recent = history.slice(-6);
  const delta = recent[recent.length - 1] - recent[0];
  const minutes = (recent.length - 1) * 2;
  return minutes > 0 ? Math.round(delta / Math.max(minutes, 1) * 60) : 0;
}

// ── Dashboard Rendering ──
function renderDashboard(container, emptyEl) {
  if (!container) return;

  const { trees, expanded, searchQuery, statusFilter } = getState();

  let filtered = trees;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(t => t.sandbox.toLowerCase().includes(q));
  }
  if (statusFilter) {
    filtered = filtered.filter(t => (t.status || '').toLowerCase() === statusFilter);
  }

  if (filtered.length === 0) {
    container.innerHTML = '';
    if (emptyEl) emptyEl.style.display = '';
    return;
  }

  if (emptyEl) emptyEl.style.display = 'none';

  container.innerHTML = filtered.map(t => {
    const isExpanded = !!expanded[t.sandbox];
    const tileClass = isActive(t.status) ? 'tile-hero' : 'tile-metric';
    return `
      <div class="card ${tileClass} sandbox-card" data-sandbox="${escapeAttr(t.sandbox)}">
        <div class="card-header tree-sandbox-header" data-sandbox="${escapeAttr(t.sandbox)}">
          <span class="tree-dot ${statusDotClass(t.status)}"></span>
          <span class="tree-sandbox-name">${escapeHtml(t.sandbox)}</span>
          <span class="badge badge-${statusBadgeClass(t.status)}">${escapeHtml(t.status)}</span>
          ${t.model ? `<span class="model-badge">${escapeHtml(t.model)}</span>` : ''}
          <span class="tree-chevron">${isExpanded ? '▼' : '▶'}</span>
        </div>
        ${isExpanded && t.tree ? `<div class="card-body">${renderTree(t.tree)}</div>` : ''}
        <div class="card-footer">
          <span class="text-xs text-dim">${(t.tokens_used || 0).toLocaleString()} tokens</span>
          <span class="text-xs text-dim">${(t.tool_calls || 0)} calls</span>
        </div>
      </div>
    `;
  }).join('');

  // Event delegation for sandbox clicks
  delegate(container, '.tree-sandbox-header', 'click', (e) => {
    const name = e.currentTarget.dataset.sandbox;
    if (name) {
      const { expanded } = getState();
      setState({ expanded: { ...expanded, [name]: !expanded[name] } });
    }
  });

  // Double-click for detail
  delegate(container, '.tree-sandbox-name', 'dblclick', (e) => {
    e.stopPropagation();
    const card = e.target.closest('.sandbox-card');
    if (card) setState({ selectedSandbox: card.dataset.sandbox });
  });

  // Single click on card body for detail
  delegate(container, '.card-body', 'click', (e) => {
    const card = e.target.closest('.sandbox-card');
    if (card) setState({ selectedSandbox: card.dataset.sandbox });
  });
}

// ── Search ──
function setupSearch() {
  const bar = qs('#search-bar');
  if (!bar) return;

  bar.innerHTML = `
    <span class="search-icon">🔍</span>
    <input type="text" id="search-input" placeholder="Search sandboxes… (Ctrl+K)" autocomplete="off">
    <select id="status-filter">
      <option value="">All statuses</option>
      <option value="active">Active</option>
      <option value="running">Running</option>
      <option value="idle">Idle</option>
      <option value="error">Error</option>
      <option value="dead">Dead</option>
    </select>
  `;

  on(qs('#search-input'), 'input', (e) => {
    setState({ searchQuery: e.target.value });
  });

  on(qs('#status-filter'), 'change', (e) => {
    setState({ statusFilter: e.target.value });
  });
}

// ── Token Prompt ──
function promptForToken() {
  const stored = getToken();
  if (stored) return;

  // Check if server requires auth by making a test request
  fetch('/api/v1/summary').then(r => {
    if (r.status === 401) {
      const token = prompt('Enter HERO Web Token:');
      if (token) setToken(token);
    }
  }).catch(() => {});
}

// ── Helpers ──
function isActive(status) {
  return ['active', 'running', 'working'].includes((status || '').toLowerCase());
}

function statusDotClass(status) {
  const s = (status || 'idle').toLowerCase();
  if (['active', 'running', 'working', 'booting'].includes(s)) return 'active';
  if (['idle', 'spawning'].includes(s)) return 'idle';
  if (['error', 'failed', 'timeout', 'blocked'].includes(s)) return 'error';
  if (['done', 'completed', 'created'].includes(s)) return 'done';
  return 'dead';
}

function statusBadgeClass(status) {
  const s = (status || 'idle').toLowerCase();
  if (['active', 'running', 'working'].includes(s)) return 'active';
  if (['idle', 'spawning'].includes(s)) return 'idle';
  if (['error', 'failed', 'timeout', 'blocked'].includes(s)) return 'error';
  if (['done', 'completed', 'created'].includes(s)) return 'done';
  return 'dead';
}

function escapeAttr(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Boot ──
document.addEventListener('DOMContentLoaded', init);
```

## DESIGN
- `index.html`: Minimal shell — just containers and script/css imports
- `js/app.js`: Wires everything — imports components, mounts them, connects SSE, handles routing
- Module graph: `app.js` → components + services → utils
- No inline `<style>` or `<script>` in index.html (except the module import)

## CONSTRAINTS
- `<script type="module">` — enables ES module imports
- CSS load order: tokens → base → layout → components → animations
- Old `app.js` (root level) must be deleted — new one is at `js/app.js`
- Old `style.css` (root level) must be deleted — replaced by `css/` directory
- All component mounting happens after DOMContentLoaded
- SSE reconnect handled by sse.js, not app.js

## ACCEPTANCE
1. `index.html` loads without errors in browser console
2. All CSS files load (check Network tab — 5 CSS files)
3. `js/app.js` loads as ES module (check Network tab)
4. Dashboard renders sandbox cards from `/api/v1/tree`
5. SSE connects and live-updates data
6. Search bar filters sandboxes in real-time
7. Click sandbox → detail drawer opens
8. Kill button → modal → confirmation → API call → toast
9. Fonts render: Orbitron headings, Share Tech Mono data
10. Glassmorphism visible on cards, drawer, modal
11. Old `app.js` and `style.css` no longer referenced
12. No console errors on clean load
