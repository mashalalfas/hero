/**
 * HERO OS — API Service
 * Wraps all FastAPI endpoints
 */

const BASE = '';

async function _fetchJSON(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  summary() {
    return _fetchJSON('/api/v1/summary');
  },
  tree() {
    return _fetchJSON('/api/v1/tree');
  },
  sandbox(name) {
    return _fetchJSON(`/api/v1/sandbox/${encodeURIComponent(name)}`);
  },
  timeline(name) {
    return _fetchJSON(`/api/v1/sandbox/${encodeURIComponent(name)}/timeline`);
  },
  bottlenecks() {
    return _fetchJSON('/api/v1/bottlenecks');
  },
  spawn(name, { task = '', model = '' } = {}) {
    return _fetchJSON(`/api/v1/sandbox/${encodeURIComponent(name)}/spawn`, {
      method: 'POST',
      body: JSON.stringify({ task, model }),
    });
  },
  kill(name) {
    return _fetchJSON(`/api/v1/sandbox/${encodeURIComponent(name)}/kill`, {
      method: 'POST',
      body: JSON.stringify({ confirmation_token: name }),
    });
  },
};
