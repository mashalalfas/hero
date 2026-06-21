/**
 * HERO OS — SSE Connection Manager
 * Auto-reconnect with exponential backoff
 */

import { getStore } from './state.js';

const SSE_URL = '/api/v1/events';
const MAX_BACKOFF = 30000;

let es = null;
let reconnectTimer = null;
let backoff = 2000;
let connected = false;

function connect() {
  if (es) {
    try { es.close(); } catch (_) { /* noop */ }
  }

  try {
    es = new EventSource(SSE_URL);
  } catch (err) {
    console.error('[SSE] failed to create EventSource:', err);
    scheduleReconnect();
    return;
  }

  es.addEventListener('open', () => {
    connected = true;
    backoff = 2000;
    _setConnection('connected');
  });

  es.addEventListener('summary', (ev) => {
    try {
      const data = JSON.parse(ev.data);
      const store = getStore('metrics');
      if (store) store.set(data);
    } catch (e) {
      console.warn('[SSE] summary parse error:', e);
    }
  });

  es.addEventListener('tree_update', () => {
    // Trigger tree refresh
    const store = getStore('ui');
    if (store) store.set({ treeRefreshTrigger: Date.now() });
  });

  es.addEventListener('error', (ev) => {
    console.warn('[SSE] error event:', ev);
    _setConnection('disconnected');
    scheduleReconnect();
  });

  es.onerror = () => {
    connected = false;
    _setConnection('disconnected');
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, backoff);
  backoff = Math.min(backoff * 1.5, MAX_BACKOFF);
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (es) {
    try { es.close(); } catch (_) { /* noop */ }
    es = null;
  }
  connected = false;
  _setConnection('disconnected');
}

function _setConnection(status) {
  const store = getStore('ui');
  if (store) store.set({ connectionStatus: status });
}

export const sse = { connect, disconnect, get connected() { return connected; } };
