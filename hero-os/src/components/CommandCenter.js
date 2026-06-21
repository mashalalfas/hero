/**
 * HERO OS — CommandCenter Component
 * Spawn / kill form with live output log.
 */

import { api } from '../services/api.js';
import { getStore } from '../services/state.js';

let _logEl = null;
let _logs = [];
const MAX_LOGS = 100;

function mount() {
  _logEl = document.getElementById('command-output');
  _bindEvents();
  _renderLog();
}

function unmount() {
  _logEl = null;
}

function _bindEvents() {
  const spawnBtn = document.getElementById('btn-spawn');
  const sandboxInput = document.getElementById('sandbox-name');
  const taskInput = document.getElementById('task-desc');
  const modelSelect = document.getElementById('model-select');

  if (!spawnBtn) return;

  spawnBtn.addEventListener('click', async () => {
    const name = (sandboxInput?.value || '').trim();
    const task = (taskInput?.value || '').trim();
    const model = modelSelect?.value || '';

    if (!name) {
      _addLog('error', 'Sandbox name is required');
      sandboxInput?.focus();
      return;
    }

    spawnBtn.disabled = true;
    _addLog('info', `Deploying army to sandbox "${name}"...`);

    try {
      const result = await api.spawn(name, { task, model });
      _addLog('success', result.message || `Spawned ${name}`);
      const treeStore = getStore('tree');
      if (treeStore) {
        api.tree().then(data => treeStore.set(data)).catch(() => {});
      }
    } catch (err) {
      _addLog('error', err.message);
    } finally {
      spawnBtn.disabled = false;
    }
  });

  // Add kill button dynamically if not present
  const form = document.querySelector('.command-form');
  if (form && !document.getElementById('btn-kill')) {
    const killBtn = document.createElement('button');
    killBtn.id = 'btn-kill';
    killBtn.className = 'btn-sm';
    killBtn.style.cssText = 'margin-top:8px;width:100%;border-color:var(--neon-red);color:var(--neon-red);';
    killBtn.innerHTML = '<span>⏹ Kill Sandbox</span>';
    form.appendChild(killBtn);

    killBtn.addEventListener('click', async () => {
      const name = (sandboxInput?.value || '').trim();
      if (!name) {
        _addLog('error', 'Sandbox name is required to kill');
        return;
      }
      if (!confirm(`Kill sandbox "${name}"?`)) return;
      killBtn.disabled = true;
      _addLog('info', `Killing sandbox "${name}"...`);
      try {
        const result = await api.kill(name);
        _addLog('success', result.message || `Killed ${name}`);
      } catch (err) {
        _addLog('error', err.message);
      } finally {
        killBtn.disabled = false;
      }
    });
  }
}

function _addLog(level, message) {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  _logs.push({ time, level, message });
  if (_logs.length > MAX_LOGS) _logs.shift();
  _renderLog();
}

function _renderLog() {
  if (!_logEl) return;
  _logEl.innerHTML = _logs.map((l) => `
    <div class="log-line">
      <span class="log-time">[${l.time}]</span>
      <span class="log-msg ${l.level}">${escapeHtml(l.message)}</span>
    </div>
  `).join('');
  _logEl.scrollTop = _logEl.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export const CommandCenter = { mount, unmount };
