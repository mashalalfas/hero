import { subscribe, getState } from '../services/state.js';
import { escapeHtml, formatNumber } from '../utils/dom.js';

export function create(container) {
  const state = getState();
  let unsubscribe;

  render(container, state);

  unsubscribe = subscribe((newState) => {
    render(container, newState);
  });

  return {
    destroy: () => {
      if (unsubscribe) unsubscribe();
    }
  };
}

function render(container, state) {
  const summary = state.summary || {};

  const tokensUsed = summary.total_tokens_used || 0;
  const tokensBudget = summary.total_tokens_budget || 0;
  const tokenPct = tokensBudget > 0 ? Math.round((tokensUsed / tokensBudget) * 100) : 0;

  // Count active/idle across all sandboxes (merged map, not just trees)
  const sandboxList = Object.values(state.sandboxes || {});
  const activeCount = sandboxList.filter(sb => {
    const s = (sb.status || '').toLowerCase();
    return ['active', 'running', 'working', 'spawning'].includes(s);
  }).length;
  const totalCount = sandboxList.length;
  const errorCount = summary.bottleneck_count || 0;

  container.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Tokens Used</div>
      <div class="stat-value">${formatNumber(tokensUsed)}</div>
      ${tokensBudget > 0 ? `
        <div class="progress-bar" style="margin: 4px 0; max-width: 200px;">
          <div class="progress-fill" style="width:${tokenPct}%"></div>
        </div>
        <div class="stat-sub">${tokenPct}% of ${formatNumber(tokensBudget)}</div>
      ` : `<div class="stat-sub">No budget data</div>`}
    </div>
    <div class="stat-card">
      <div class="stat-label">Sandboxes</div>
      <div class="stat-value">${formatNumber(activeCount)}</div>
      <div class="stat-sub">${formatNumber(totalCount)} total</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Errors</div>
      <div class="stat-value" style="${errorCount > 0 ? 'color: var(--color-danger);' : ''}">${formatNumber(errorCount)}</div>
      <div class="stat-sub">bottlenecks</div>
    </div>
  `;
}
