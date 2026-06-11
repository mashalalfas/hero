import { escapeHtml, escapeAttr } from '../utils/dom.js';

let activeModal = null;

/**
 * Show a confirmation modal overlay.
 * @param {Object} options
 * @param {string} options.title - Modal title
 * @param {string} options.message - Modal body text (may contain HTML)
 * @param {string} [options.confirmText='Confirm'] - Confirm button label
 * @param {string} [options.cancelText='Cancel'] - Cancel button label
 * @param {string} [options.confirmClass=''] - Additional class for confirm button (e.g. 'danger')
 * @param {Function} [options.onConfirm] - Called when confirmed
 * @param {Function} [options.onCancel] - Called when cancelled (optional)
 */
export function showModal({
  title = 'Confirm',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmClass = '',
  onConfirm,
  onCancel
} = {}) {
  // Remove any existing modal
  closeModal();

  const modalId = `modal-${Date.now()}`;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = modalId;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', `${modalId}-title`);
  overlay.innerHTML = `
    <div class="modal-glass">
      <div class="modal-content">
        <div class="modal-header">
          <h3 id="${modalId}-title" class="modal-title">${escapeHtml(title)}</h3>
          <button class="modal-close-btn" aria-label="Close modal" type="button">&times;</button>
        </div>
        <div class="modal-body">${message}</div>
        <div class="modal-footer">
          <button class="modal-btn modal-btn-cancel" data-action="cancel" type="button">${escapeHtml(cancelText)}</button>
          <button class="modal-btn modal-btn-confirm ${escapeAttr(confirmClass)}" data-action="confirm" type="button">${escapeHtml(confirmText)}</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
  // Use requestAnimationFrame to ensure the initial opacity:0 is painted
  // before transitioning to opacity:1. This prevents mobile browsers from
  // skipping the CSS transition on freshly appended elements.
  requestAnimationFrame(() => {
    overlay.classList.add('show');
  });

  // Track focusable elements for focus trap
  const focusable = overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const firstFocusable = focusable[0];
  const lastFocusable = focusable[focusable.length - 1];

  // Focus the cancel button by default
  const cancelBtn = overlay.querySelector('[data-action="cancel"]');
  if (cancelBtn) cancelBtn.focus();

  activeModal = {
    id: modalId,
    overlay,
    onConfirm,
    onCancel
  };

  // --- Event handlers ---

  function handleConfirm() {
    closeModal();
    if (typeof onConfirm === 'function') onConfirm();
  }

  function handleCancel() {
    closeModal();
    if (typeof onCancel === 'function') onCancel();
  }

  function handleBackdropClick(e) {
    if (e.target === overlay || e.target.classList.contains('modal-glass')) {
      handleCancel();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
      return;
    }

    if (e.key === 'Enter') {
      // Only trigger confirm if not focused on cancel button
      if (document.activeElement?.dataset?.action !== 'cancel' &&
          document.activeElement?.dataset?.action !== 'confirm') {
        e.preventDefault();
        handleConfirm();
      }
      return;
    }

    // Focus trap
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === firstFocusable) {
          e.preventDefault();
          lastFocusable?.focus();
        }
      } else {
        if (document.activeElement === lastFocusable) {
          e.preventDefault();
          firstFocusable?.focus();
        }
      }
    }
  }

  // Confirm button
  const confirmBtn = overlay.querySelector('[data-action="confirm"]');
  if (confirmBtn) confirmBtn.addEventListener('click', handleConfirm);

  // Cancel button
  if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);

  // Close button
  const closeBtn = overlay.querySelector('.modal-close-btn');
  if (closeBtn) closeBtn.addEventListener('click', handleCancel);

  // Backdrop click
  overlay.addEventListener('click', handleBackdropClick);

  // Keyboard
  document.addEventListener('keydown', handleKeydown);

  // Store refs for cleanup
  overlay._handlers = { handleConfirm, handleCancel, handleBackdropClick, handleKeydown };
}

/**
 * Close the currently active modal.
 */
export function closeModal() {
  if (!activeModal) return;

  const { overlay } = activeModal;
  if (overlay && overlay.parentNode) {
    const handlers = overlay._handlers || {};

    // Remove event listeners
    const confirmBtn = overlay.querySelector('[data-action="confirm"]');
    const cancelBtn = overlay.querySelector('[data-action="cancel"]');
    const closeBtn = overlay.querySelector('.modal-close-btn');

    if (confirmBtn) confirmBtn.removeEventListener('click', handlers.handleConfirm);
    if (cancelBtn) cancelBtn.removeEventListener('click', handlers.handleCancel);
    if (closeBtn) closeBtn.removeEventListener('click', handlers.handleCancel);
    overlay.removeEventListener('click', handlers.handleBackdropClick);
    if (handlers.handleKeydown) {
      document.removeEventListener('keydown', handlers.handleKeydown);
    }

    // Exit animation, then remove
    overlay.classList.add('modal-exit');
    setTimeout(() => {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }, 300);
  }

  activeModal = null;
}
