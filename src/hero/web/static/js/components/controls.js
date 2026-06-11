import { killSandbox } from '../services/api.js';
import { escapeAttr } from '../utils/dom.js';
import { showToast } from './toast.js';
import { showModal } from './modal.js';

/**
 * Render sandbox control buttons (e.g. kill) into a container.
 * Uses DIRECT handlers on the button element (not event delegation)
 * to avoid race conditions with DOM re-renders on mobile.
 *
 * @param {HTMLElement} container
 * @param {string} sandboxName
 * @param {string} [status] - Sandbox status; kill button shown only for active/running
 */
export function renderControls(container, sandboxName, status) {
  if (!container) return;

  const name = sandboxName || '';
  const st = (status || '').toLowerCase();
  const isActive = st === 'active' || st === 'running' || st === 'working';

  container.innerHTML = `
    <div class="sandbox-controls" data-sandbox="${escapeAttr(name)}" data-status="${escapeAttr(st)}">
      ${isActive ? `
      <button class="btn-kill" data-action="kill" type="button" title="Kill sandbox: ${name}">
        <span aria-hidden="true">☠️</span> Kill
      </button>` : ''}
    </div>
  `;

  // Wire DIRECT handler on the button (not delegation)
  const btn = container.querySelector('.btn-kill');
  if (!btn) return;

  // Fire-once guard: touchend fires first on mobile, then click.
  // We handle touchend (with preventDefault) as primary, click as fallback.
  let handled = false;

  function showConfirm() {
    if (handled) return;
    handled = true;
    // Reset guard after a short delay
    setTimeout(() => { handled = false; }, 400);

    console.debug('[controls] Kill confirm triggered for', name);

    showModal({
      title: 'Kill Sandbox',
      message: `Are you sure you want to kill <strong>${escapeAttr(name)}</strong>? This will terminate the sandbox and all running tasks.`,
      confirmText: '☠️ Kill',
      confirmClass: 'danger',
      onConfirm: async () => {
        try {
          console.debug('[controls] Sending kill for', name);
          await killSandbox(name, name);
          showToast(`Sandbox ${name} killed successfully`, 'success');
          window.dispatchEvent(new CustomEvent('hero:refresh'));
        } catch (err) {
          showToast(`Failed to kill ${name}: ${err.message}`, 'error');
        }
      },
      onCancel: () => {
        showToast('Kill cancelled', 'info');
      }
    });
  }

  // Primary for mobile: touchend fires before click, no 300ms delay
  btn.addEventListener('touchend', (e) => {
    // Only handle if finger released over the button
    const touch = e.changedTouches?.[0];
    if (touch) {
      const r = btn.getBoundingClientRect();
      const x = touch.clientX;
      const y = touch.clientY;
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return;
    }
    e.preventDefault(); // Prevent duplicate click event
    showConfirm();
  }, { passive: false });

  // Secondary for desktop: click event
  btn.addEventListener('click', () => {
    showConfirm();
  });

  // Return cleanup
  return {
    destroy: () => {
      container.innerHTML = '';
    }
  };
}
