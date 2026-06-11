import { subscribe, getState, setState } from '../services/state.js';
import { escapeHtml, escapeAttr, formatNumber, $ } from '../utils/dom.js';
import { renderTree } from './tree-node.js';
import { renderControls } from './controls.js';

export function create(container) {
  const state = getState();
  let unsubscribe;

  render(container, state);

  // Delegate click: clicking a card opens detail drawer
  // BUT skip if the click landed on a kill button or its container
  container.addEventListener('click', (e) => {
    if (e.target.closest('.kill-btn-container, [data-action="kill"]')) return;
    const card = e.target.closest('[data-sandbox-name]');
    if (!card) return;
    const name = card.dataset.sandboxName;
    if (!name) return;
    setState({ selectedSandbox: name });
  });

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
  // Build full sandbox list: tree data (active pipelines) merged with summary (all sandboxes)
  const trees = state.trees || [];
  const allSandboxes = [ ...trees ];
  for (const [name, sb] of Object.entries(state.sandboxes || {})) {
    if (!allSandboxes.find(t => t.sandbox === name)) {
      allSandboxes.push(sb);
    }
  }

  if (!allSandboxes.length) {
    container.innerHTML = '';
    const empty = $('#empty-state');
    if (empty) empty.style.display = '';
    return;
  }

  const empty = $('#empty-state');
  if (empty) empty.style.display = 'none';

  container.innerHTML = `
    <div class="sandbox-grid">
      ${allSandboxes.map(sb => renderCard(sb)).join('')}
    </div>
  `;

  // Wire kill buttons after DOM rendered
  allSandboxes.forEach(sb => {
    const status = (sb.status || '').toLowerCase();
    const killContainer = container.querySelector(`.kill-btn-container[data-sandbox="${escapeAttr(sb.sandbox)}"]`);
    if (killContainer && ['active', 'running', 'working', 'spawning'].includes(status)) {
      renderControls(killContainer, sb.sandbox, status);
    }
  });
}

function renderCard(sb) {
  const name = sb.sandbox || 'unknown';
  const status = (sb.status || 'idle').toLowerCase();
  const model = sb.model || '';
  const tokensUsed = sb.tokens_used || 0;
  const tokensBudget = sb.tokens_budget || 0;
  const tokenPct = tokensBudget > 0 ? Math.min(100, Math.round((tokensUsed / tokensBudget) * 100)) : 0;
  const isActive = ['active', 'running', 'working', 'spawning'].includes(status);

  // Tree rendering — only show if there are children (active processes)
  const tree = sb.tree || null;
  const hasChildren = tree && tree.children && tree.children.length > 0;
  const treeHtml = tree && hasChildren ? renderTree(tree) : '';

  return `
    <div class="card" data-sandbox-name="${escapeAttr(name)}" data-sandbox-status="${escapeAttr(status)}">
      <div class="card-header">
        <span class="card-title">${escapeHtml(name)}</span>
        <span class="badge badge-${status}">${escapeHtml(status)}</span>
        ${model ? `<span class="model-badge">${escapeHtml(model)}</span>` : ''}
        <span class="tree-toggle" data-sandbox="${escapeAttr(name)}" style="cursor:pointer;color:var(--color-muted-foreground);font-size:11px;
          ${hasChildren ? '' : 'display:none;'}
        ">${hasChildren ? '▾ details' : ''}</span>
      </div>
      <div class="card-body tree-body" data-sandbox="${escapeAttr(name)}">
        ${hasChildren ? treeHtml : '<div style="font-size:var(--text-sm);color:var(--color-muted-foreground);padding:4px 0;">No active agents — sandbox is ' + status + '</div>'}
      </div>
      <div class="card-footer">
        <div class="stat-pill">
          <span class="stat-label">Tokens</span>
          <span class="stat-value">${formatNumber(tokensUsed)}</span>
          <span class="stat-sub">/ ${formatNumber(tokensBudget)}</span>
        </div>
        ${tokensBudget > 0 ? `
          <div class="progress-bar" style="flex:1;margin:0 var(--space-3);">
            <div class="progress-fill" style="width:${tokenPct}%"></div>
          </div>
        ` : ''}
        ${isActive ? `
          <div class="kill-btn-container" data-sandbox="${escapeAttr(name)}"></div>
        ` : ''}
      </div>
    </div>
  `;
}
