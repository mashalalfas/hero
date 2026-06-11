import { subscribe, getState } from '../services/state.js';
import { escapeHtml } from '../utils/dom.js';

export function create(container) {
  const state = getState();
  let unsubscribe;

  container.innerHTML = `
    <div class="header-logo">
      <span class="logo-icon">⚡</span>
      <span style="font-weight: 600;">HERO</span>
      <span style="font-size: var(--text-xs); color: var(--text-tertiary); margin-left: var(--space-2);">Viewport</span>
    </div>
    <div class="header-right">
      <div class="live-indicator ${state.isConnected ? 'connected' : 'disconnected'}">
        <span class="live-dot"></span>
        <span class="live-label">${state.isConnected ? 'LIVE' : 'OFFLINE'}</span>
      </div>
    </div>
  `;

  unsubscribe = subscribe((newState) => {
    const indicator = container.querySelector('.live-indicator');
    if (!indicator) return;
    indicator.className = `live-indicator ${newState.isConnected ? 'connected' : 'disconnected'}`;
    const label = indicator.querySelector('.live-label');
    if (label) label.textContent = newState.isConnected ? 'LIVE' : 'OFFLINE';
  });

  return { destroy: () => { if (unsubscribe) unsubscribe(); } };
}
