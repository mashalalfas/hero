import { escapeHtml } from '../utils/dom.js';

const TOAST_DEFAULTS = {
  type: 'info',
  duration: 4000,
  maxVisible: 3
};

let container = null;
let activeToasts = [];
let toastCounter = 0;

/**
 * Initialize the toast container element.
 * Creates it if it doesn't exist, appended to document body.
 */
export function initToastContainer() {
  if (container && document.body.contains(container)) return;

  container = document.createElement('div');
  container.id = 'toast-container';
  container.className = 'toast-container';
  container.setAttribute('aria-live', 'polite');
  container.setAttribute('aria-label', 'Notifications');
  document.body.appendChild(container);

  // Reset tracking if container was recreated
  activeToasts = [];
}

/**
 * Show a toast notification.
 * @param {string} message - The message to display
 * @param {'success'|'error'|'info'|'warning'} [type='info']
 * @param {number} [duration=4000] - Auto-dismiss in ms. 0 = persistent.
 */
export function showToast(message, type, duration) {
  initToastContainer();

  const resolvedType = type || TOAST_DEFAULTS.type;
  const resolvedDuration = duration !== undefined ? duration : TOAST_DEFAULTS.duration;
  const id = ++toastCounter;

  // Enforce max visible
  while (activeToasts.length >= TOAST_DEFAULTS.maxVisible) {
    const oldest = activeToasts.shift();
    dismissToast(oldest);
  }

  const toastEl = document.createElement('div');
  toastEl.className = `toast toast-${resolvedType}`;
  toastEl.dataset.toastId = id;
  toastEl.setAttribute('role', 'alert');

  toastEl.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon" aria-hidden="true">${typeIcon(resolvedType)}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
    </div>
    <button class="toast-dismiss" aria-label="Dismiss notification" type="button">&times;</button>
  `;

  // Dismiss button
  const dismissBtn = toastEl.querySelector('.toast-dismiss');
  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      dismissToast(id);
    });
  }

  container.appendChild(toastEl);
  activeToasts.push(id);

  // Trigger enter animation
  requestAnimationFrame(() => {
    toastEl.classList.add('toast-visible');
  });

  // Auto-dismiss
  if (resolvedDuration > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, resolvedDuration);
  }
}

function dismissToast(id) {
  const idx = activeToasts.indexOf(id);
  if (idx !== -1) activeToasts.splice(idx, 1);

  const el = container?.querySelector(`[data-toast-id="${id}"]`);
  if (!el) return;

  el.classList.remove('toast-visible');
  el.classList.add('toast-exit');

  // Remove from DOM after animation
  setTimeout(() => {
    if (el.parentNode) el.parentNode.removeChild(el);
  }, 300);
}

function typeIcon(type) {
  switch (type) {
    case 'success': return '✓';
    case 'error': return '✕';
    case 'warning': return '⚠';
    case 'info':
    default: return 'ℹ';
  }
}

/**
 * Convenience methods
 */
export function showSuccessToast(message, duration) {
  showToast(message, 'success', duration);
}

export function showErrorToast(message, duration) {
  showToast(message, 'error', duration);
}

export function showInfoToast(message, duration) {
  showToast(message, 'info', duration);
}

export function showWarningToast(message, duration) {
  showToast(message, 'warning', duration);
}
