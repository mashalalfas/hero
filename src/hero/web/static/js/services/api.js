/* HERO Viewport — services/api.js */
import { getToken } from './auth.js';

const BASE = '';

export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('auth:expired'));
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export const fetchTree = () => apiFetch('/api/v1/tree');
export const fetchSummary = () => apiFetch('/api/v1/summary');
export const fetchSandbox = (name) => apiFetch(`/api/v1/sandbox/${encodeURIComponent(name)}`);
export const fetchBottlenecks = () => apiFetch('/api/v1/bottlenecks');

export function killSandbox(name, confirmToken) {
  return apiFetch(`/api/v1/sandbox/${encodeURIComponent(name)}/kill`, {
    method: 'POST',
    body: JSON.stringify({ confirmation_token: confirmToken }),
  });
}

export function spawnSandbox(name, task) {
  return apiFetch(`/api/v1/sandbox/${encodeURIComponent(name)}/spawn`, {
    method: 'POST',
    body: JSON.stringify({ task }),
  });
}
