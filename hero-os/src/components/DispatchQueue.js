/**
 * HERO OS — DispatchQueue Component
 * Lists pending/queued tasks from /api/v1/tree data.
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

  const refreshBtn = document.getElementById('btn-refresh-queue');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      try {
        const data = await api.tree();
        const treeStore = getStore('tree');
        if (treeStore) treeStore.set(data);
      } catch (err) {
        console.error('refresh queue error:', err);
      } finally {
        refreshBtn.disabled = false;
      }
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

  const queueItems = _extractQueueItems(trees);

  if (!queueItems.length) {
    _container.innerHTML = '<div class="empty-queue">No pending tasks</div>';
    return;
  }

  queueItems.forEach((item) => {
    const el = document.createElement('div');
    el.className = 'queue-item';
    el.innerHTML = `
      <span class="queue-icon">${item.icon}</span>
      <div class="queue-info">
        <div class="queue-role">${item.role} — ${item.sandbox}</div>
        <div class="queue-desc">${escapeHtml(item.task)}</div>
      </div>
      <span class="queue-meta">${item.status}</span>
    `;
    el.addEventListener('click', () => _showQueueDetail(item));
    _container.appendChild(el);
  });
}

function _extractQueueItems(trees) {
  const items = [];
  const queuedStatuses = ['queued', 'pending', 'dispatched', 'spawning', 'booting'];

  trees.forEach((treeItem) => {
    const tree = treeItem.tree;
    if (!tree) return;

    const walk = (node) => {
      if (!node) return;
      const status = (node.status || 'idle').toLowerCase();
      if (queuedStatuses.includes(status)) {
        items.push({
          role: (node.role || 'UNKNOWN').toUpperCase(),
          sandbox: treeItem.sandbox,
          task: node.task || node.label || '—',
          status,
          icon: _roleIcon(node.role),
        });
      }
      (node.children || []).forEach((c) => walk(c));
    };

    walk(tree);
  });

  return items;
}

function _roleIcon(role) {
  const map = {
    comm: '⚡', lead: '🎯', arch: '🏗️',
    soldier: '🤖', verify: '🔍', archivist: '📦',
  };
  return map[(role || '').toLowerCase()] || '•';
}

function _showQueueDetail(item) {
  const ui = getStore('ui');
  if (!ui) return;
  ui.set({
    modalOpen: true,
    modalTitle: `${item.icon} ${item.role}`,
    modalBody: `Sandbox: ${item.sandbox}\nStatus: ${item.status}\nTask: ${item.task}`,
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export const DispatchQueue = { mount, unmount, render };
