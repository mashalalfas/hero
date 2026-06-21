/**
 * HERO OS — AgentGrid Component
 * Card grid showing all active agents from /api/v1/tree with role/model/status.
 * Click opens modal detail.
 */

import { getStore } from '../services/state.js';
import { api } from '../services/api.js';

let _container = null;
let _unsub = null;
let _currentTrees = [];

function mount(selector) {
  _container = document.querySelector(selector);
  if (!_container) return;
  render([]);

  const store = getStore('tree');
  if (store) {
    _unsub = store.subscribe((state) => {
      _currentTrees = state.trees || [];
      render(_currentTrees);
    });
  }
}

function unmount() {
  if (_unsub) { _unsub(); _unsub = null; }
  _container = null;
}

function render(trees) {
  if (!_container) return;
  _container.innerHTML = '';

  const agents = _extractAgents(trees);

  // Update header badge
  const badge = document.getElementById('agent-count');
  if (badge) {
    const activeCount = agents.filter(a => ['running', 'active', 'working'].includes(a.status)).length;
    badge.textContent = `${activeCount} active`;
  }

  if (!agents.length) {
    _container.innerHTML = '<div class="empty-queue">No active agents</div>';
    return;
  }

  agents.forEach((agent) => {
    const card = document.createElement('div');
    card.className = 'agent-card';
    card.innerHTML = `
      <span class="agent-role">${agent.role}</span>
      <span class="agent-name">${escapeHtml(agent.name)}</span>
      <span class="agent-model">${escapeHtml(agent.model || 'auto')}</span>
      <span class="agent-status-dot ${agent.status}"></span>
    `;
    card.addEventListener('click', () => _openAgentDetail(agent));
    _container.appendChild(card);
  });
}

function _extractAgents(trees) {
  const agents = [];
  const seen = new Set();

  trees.forEach((treeItem) => {
    const tree = treeItem.tree;
    if (!tree) return;

    const walk = (node, depth = 0) => {
      if (!node) return;
      const role = (node.role || '').toUpperCase();
      const name = node.label || node.role || 'unknown';
      const key = `${treeItem.sandbox}::${name}`;

      if (!seen.has(key)) {
        seen.add(key);
        agents.push({
          role,
          name,
          model: node.model || treeItem.model || '',
          status: (node.status || 'idle').toLowerCase(),
          sandbox: treeItem.sandbox,
          task: node.task || '',
          depth,
        });
      }

      (node.children || []).forEach((c) => walk(c, depth + 1));
    };

    walk(tree);
  });

  return agents;
}

async function _openAgentDetail(agent) {
  const ui = getStore('ui');
  if (!ui) return;

  ui.set({
    modalOpen: true,
    modalTitle: `${agent.role}: ${agent.name}`,
    modalBody: 'Loading...',
  });

  try {
    const detail = await api.sandbox(agent.sandbox);
    const body = `
Role: ${agent.role}
Sandbox: ${agent.sandbox}
Model: ${agent.model || 'auto'}
Status: ${agent.status}
Task: ${agent.task || '—'}

${JSON.stringify(detail, null, 2).slice(0, 2000)}
    `.trim();
    ui.set({ modalBody: body });
  } catch (err) {
    ui.set({ modalBody: `Error loading detail: ${err.message}` });
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export const AgentGrid = { mount, unmount, render };
