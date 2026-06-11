// app.js — HERO Viewport v3 entry point
// Notion-style minimal dashboard

import { getState, setState, subscribe } from './services/state.js';
import { getToken } from './services/auth.js';
import { SSEManager } from './services/sse.js';
import { fetchTree, fetchSummary } from './services/api.js';
import { $ } from './utils/dom.js';
import { create as createHeader } from './components/header.js';
import { create as createStatsBar } from './components/stats-bar.js';
import { create as createSandboxCard } from './components/sandbox-card.js';
import { create as createDetailPanel } from './components/detail-panel.js';
import { initToastContainer, showToast } from './components/toast.js';

// ── SSE ──────────────────────────────────────────────────
const sse = new SSEManager('/api/v1/events');

function connectSSE() {
  const token = getToken();
  if (token) { sse.connect(token); } else { sse.connect(); }
  sse.on('summary', (data) => {
    const current = getState();
    const sandboxes = { ...(current.sandboxes || {}) };
    // Merge in any sandboxes from SSE summary that aren't already in the map
    for (const s of data?.sandboxes || []) {
      if (!sandboxes[s.name]) {
        sandboxes[s.name] = {
          sandbox: s.name,
          status: s.status || 'idle',
          model: s.model || null,
          tokens_used: s.tokens_used || 0,
          tokens_budget: s.tokens_budget || 0,
          tool_calls: s.tool_calls || 0,
          tree: null,
        };
      }
    }
    setState({ summary: data, sandboxes, isConnected: true });
  });
  sse.on('error', () => setState({ isConnected: false }));
}

// ── Data Fetching ────────────────────────────────────────
async function loadData() {
  try {
    const [treeData, summaryData] = await Promise.all([
      fetchTree(),
      fetchSummary(),
    ]);

    // Build sandboxes map: merge tree data + summary sandboxes
    // Tree endpoint only returns active pipelines, summary has all sandboxes
    const sandboxes = {};
    for (const t of treeData.trees || []) {
      sandboxes[t.sandbox] = t;
    }
    // Add any sandboxes from summary that tree omitted (dead/idle)
    for (const s of summaryData?.sandboxes || []) {
      if (!sandboxes[s.name]) {
        sandboxes[s.name] = {
          sandbox: s.name,
          status: s.status || 'idle',
          model: s.model || null,
          tokens_used: s.tokens_used || 0,
          tokens_budget: s.tokens_budget || 0,
          tool_calls: s.tool_calls || 0,
          tree: null,
        };
      }
    }

    setState({
      trees: treeData.trees || [],
      sandboxes,
      summary: summaryData,
      isConnected: true,
    });

    // Token history for sparkline
    const total = summaryData?.total_tokens_used || 0;
    const history = getState().tokenHistory || [];
    history.push(total);
    if (history.length > 20) history.shift();
    setState({ tokenHistory: history });
  } catch (err) {
    setState({ isConnected: false });
    showToast('Failed to load dashboard data', 'error');
  }
}

// ── Init ─────────────────────────────────────────────────
async function init() {
  initToastContainer();

  // Mount header
  const headerEl = $('#header');
  if (headerEl) createHeader(headerEl);

  // Mount stats bar
  const statsEl = $('#stats-bar');
  if (statsEl) createStatsBar(statsEl);

  // Mount sandbox card grid
  const gridEl = $('#sandbox-grid');
  if (gridEl) createSandboxCard(gridEl);

  // Mount detail drawer
  const drawerEl = $('#detail-drawer');
  if (drawerEl) createDetailPanel(drawerEl);

  // Load initial data
  loadData();
  connectSSE();

  // Listen for manual refresh trigger (e.g. after kill action)
  window.addEventListener('hero:refresh', () => {
    loadData();
  });

  // Periodic refresh fallback
  setInterval(loadData, 10000);
}

document.addEventListener('DOMContentLoaded', init);
