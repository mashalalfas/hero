/**
 * HERO OS — Main Application
 * Wires SSE, state, components, and modal.
 */

import { createStore } from './services/state.js';
import { api } from './services/api.js';
import { sse } from './services/sse.js';
import { PipelineFlow } from './components/PipelineFlow.js';
import { AgentGrid } from './components/AgentGrid.js';
import { CommandCenter } from './components/CommandCenter.js';
import { DispatchQueue } from './components/DispatchQueue.js';

// ── Stores ────────────────────────────────────────────────────
const metricsStore = createStore('metrics', {
  sandboxes: [], tokens_used: 0, tokens_budget: 0, tool_calls: 0,
});

const treeStore = createStore('tree', { trees: [] });

const uiStore = createStore('ui', {
  connectionStatus: 'connecting',
  modalOpen: false,
  modalTitle: '',
  modalBody: '',
});

// ── Metrics updater ───────────────────────────────────────────
function updateHeaderMetrics(metrics) {
  const tokensEl = document.getElementById('metric-tokens');
  const agentsEl = document.getElementById('metric-agents');
  const callsEl = document.getElementById('metric-calls');

  let totalTokens = 0;
  let totalCalls = 0;
  let activeAgents = 0;

  const sandboxes = metrics.sandboxes || [];
  sandboxes.forEach((s) => {
    totalTokens += s.tokens_used || 0;
    totalCalls += s.tool_calls || 0;
    const st = (s.status || '').toLowerCase();
    if (['active', 'running', 'working'].includes(st)) activeAgents++;
  });

  if (tokensEl) tokensEl.textContent = totalTokens.toLocaleString();
  if (agentsEl) agentsEl.textContent = activeAgents.toLocaleString();
  if (callsEl) callsEl.textContent = totalCalls.toLocaleString();
}

// ── Connection status ─────────────────────────────────────────
function updateConnectionStatus(status) {
  const indicator = document.getElementById('connection-status');
  const text = document.getElementById('connection-text');
  if (!indicator || !text) return;

  indicator.className = 'status-indicator';
  if (status === 'connected') {
    indicator.classList.add('connected');
    text.textContent = 'Live';
  } else if (status === 'disconnected') {
    indicator.classList.add('disconnected');
    text.textContent = 'Reconnecting...';
  } else {
    text.textContent = 'Connecting...';
  }
}

// ── Modal ─────────────────────────────────────────────────────
function initModal() {
  const overlay = document.getElementById('modal-overlay');
  const closeBtn = document.getElementById('modal-close');
  const titleEl = document.getElementById('modal-title');
  const bodyEl = document.getElementById('modal-body');

  if (!overlay) return;

  uiStore.subscribe((state) => {
    if (state.modalOpen) {
      overlay.classList.add('show');
      if (titleEl) titleEl.textContent = state.modalTitle;
      if (bodyEl) {
        bodyEl.innerHTML = `<pre style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(state.modalBody)}</pre>`;
      }
    } else {
      overlay.classList.remove('show');
    }
  });

  closeBtn?.addEventListener('click', () => uiStore.set({ modalOpen: false }));
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) uiStore.set({ modalOpen: false });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') uiStore.set({ modalOpen: false });
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Data sync ─────────────────────────────────────────────────
async function refreshTree() {
  try {
    const data = await api.tree();
    treeStore.set(data);
  } catch (err) {
    console.error('refreshTree error:', err);
  }
}

async function refreshMetrics() {
  try {
    const data = await api.summary();
    metricsStore.set(data);
    updateHeaderMetrics(data);
  } catch (err) {
    console.error('refreshMetrics error:', err);
  }
}

// ── Pipeline zoom controls ────────────────────────────────────
function initZoomControls() {
  const flow = document.getElementById('pipeline-flow');
  const container = document.getElementById('pipeline-container');
  if (!flow || !container) return;

  let scale = 1;
  const btnIn = document.getElementById('btn-zoom-in');
  const btnOut = document.getElementById('btn-zoom-out');
  const btnReset = document.getElementById('btn-zoom-reset');

  btnIn?.addEventListener('click', () => {
    scale = Math.min(scale + 0.1, 2);
    flow.style.transform = `scale(${scale})`;
    flow.style.transformOrigin = 'left center';
  });

  btnOut?.addEventListener('click', () => {
    scale = Math.max(scale - 0.1, 0.5);
    flow.style.transform = `scale(${scale})`;
    flow.style.transformOrigin = 'left center';
  });

  btnReset?.addEventListener('click', () => {
    scale = 1;
    flow.style.transform = 'scale(1)';
  });
}

// ── Init ──────────────────────────────────────────────────────
function init() {
  // Subscribe stores
  metricsStore.subscribe(updateHeaderMetrics);
  uiStore.subscribe((state) => updateConnectionStatus(state.connectionStatus));

  // SSE tree_update instant refresh (falls back to 5s poll)
  let lastTreeRefresh = 0;
  uiStore.subscribe((state) => {
    if (state.treeRefreshTrigger && state.treeRefreshTrigger !== lastTreeRefresh) {
      lastTreeRefresh = state.treeRefreshTrigger;
      refreshTree();
    }
  });

  // Mount components
  PipelineFlow.mount('#pipeline-flow');
  AgentGrid.mount('#agents-grid');
  CommandCenter.mount();
  DispatchQueue.mount('#queue-list');

  // Modal + controls
  initModal();
  initZoomControls();

  // Initial data load
  refreshTree();
  refreshMetrics();

  // SSE
  sse.connect();

  // Periodic refresh fallback
  setInterval(() => {
    refreshTree();
    refreshMetrics();
  }, 5000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
