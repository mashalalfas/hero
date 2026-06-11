import { subscribe, getState } from '../services/state.js';
import { fetchSandbox } from '../services/api.js';
import { escapeHtml, escapeAttr, formatNumber, timeAgo } from '../utils/dom.js';
import { renderTimeline } from './timeline.js';

export function create(container) {
  let unsubscribe;
  let currentSandbox = null;
  let panelEl = null;
  let backdropEl = null;

  function initPanel() {
    if (!panelEl) {
      panelEl = document.createElement('div');
      panelEl.id = 'detail-panel';
      panelEl.className = 'drawer';
      panelEl.setAttribute('role', 'dialog');
      panelEl.setAttribute('aria-modal', 'true');
      panelEl.setAttribute('aria-labelledby', 'detail-panel-title');
      panelEl.style.display = 'none';
      container.appendChild(panelEl);

      backdropEl = document.createElement('div');
      backdropEl.className = 'drawer-backdrop';
      backdropEl.style.display = 'none';
      container.appendChild(backdropEl);

      // Close on backdrop click
      backdropEl.addEventListener('click', closePanel);
    }
  }

  function closePanel() {
    if (panelEl) panelEl.style.display = 'none';
    if (backdropEl) backdropEl.style.display = 'none';
    document.removeEventListener('keydown', handleKeydown);
    const { setState } = getState();
    if (typeof setState === 'function') {
      setState({ selectedSandbox: null });
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      closePanel();
    }
  }

  function openPanel(name) {
    initPanel();
    currentSandbox = name;

    panelEl.innerHTML = `
      <div class="drawer-header">
        <h2 id="detail-panel-title" class="drawer-header-title">${escapeHtml(name)}</h2>
        <button class="drawer-close" aria-label="Close panel" type="button">&times;</button>
      </div>
      <div class="drawer-body">
        <div class="drawer-loading">
          <div class="spinner" aria-hidden="true"></div>
          <span>Loading sandbox details…</span>
        </div>
      </div>
      <div class="drawer-sections"></div>
    `;

    panelEl.style.display = '';
    backdropEl.style.display = '';
    document.addEventListener('keydown', handleKeydown);

    // Close button
    const closeBtn = panelEl.querySelector('.drawer-close');
    if (closeBtn) closeBtn.addEventListener('click', closePanel);

    // Fetch data
    loadSandboxData(name);
  }

  async function loadSandboxData(name) {
    const sectionsEl = panelEl.querySelector('.drawer-sections');
    const loadingEl = panelEl.querySelector('.drawer-loading');
    if (!sectionsEl) return;

    try {
      const [sandboxData, timelineData] = await Promise.all([
        fetchSandbox(name),
        fetchSandboxTimeline(name)
      ]);

      if (loadingEl) loadingEl.style.display = 'none';
      sectionsEl.innerHTML = buildSections(sandboxData, timelineData);
    } catch (err) {
      if (loadingEl) {
        loadingEl.innerHTML = `<div class="drawer-error">Failed to load: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  async function fetchSandboxTimeline(name) {
    try {
      const resp = await fetch(`/api/v1/sandbox/${encodeURIComponent(name)}/timeline`);
      if (!resp.ok) return [];
      return await resp.json();
    } catch {
      return [];
    }
  }

  function buildSections(sandbox, timeline) {
    const sections = [];

    // Budget section
    const tokensUsed = sandbox.tokensUsed || 0;
    const tokenBudget = sandbox.tokenBudget || 1;
    const tokenPct = Math.min(100, Math.round((tokensUsed / tokenBudget) * 100));
    sections.push(`
      <section class="drawer-section section-budget">
        <h3 class="section-title">Budget</h3>
        <div class="metric-progress large">
          <div class="progress-track">
            <div class="progress-fill ${tokenBarClass(tokenPct)}" style="width: ${tokenPct}%"></div>
          </div>
          <span class="progress-label">${escapeHtml(formatNumber(tokensUsed))} / ${escapeHtml(formatNumber(tokenBudget))} (${tokenPct}%)</span>
        </div>
      </section>
    `);

    // Pipeline section
    const pipeline = sandbox.pipeline || {};
    const pipelineSteps = pipeline.steps || [];
    sections.push(`
      <section class="drawer-section section-pipeline">
        <h3 class="section-title">Pipeline</h3>
        ${pipelineSteps.length > 0
          ? `<ol class="pipeline-steps">${pipelineSteps.map(step => `
            <li class="pipeline-step status-${step.status || 'pending'}">
              <span class="step-name">${escapeHtml(step.name || 'Step')}</span>
              ${step.duration ? `<span class="step-duration">${escapeHtml(step.duration)}</span>` : ''}
            </li>`).join('')}</ol>`
          : '<p class="section-empty">No pipeline data</p>'
        }
      </section>
    `);

    // Dispatch tasks section
    const tasks = sandbox.tasks || sandbox.dispatchTasks || [];
    sections.push(`
      <section class="drawer-section section-tasks">
        <h3 class="section-title">Dispatch Tasks</h3>
        ${tasks.length > 0
          ? `<ul class="task-list">${tasks.map(t => `
            <li class="task-item status-${t.status || 'pending'}">
              <span class="task-text">${escapeHtml(t.task || t.name || 'Unnamed task')}</span>
              <span class="task-status">${escapeHtml(t.status || 'pending')}</span>
            </li>`).join('')}</ul>`
          : '<p class="section-empty">No pending tasks</p>'
        }
      </section>
    `);

    // Errors section
    const errors = sandbox.errors || [];
    sections.push(`
      <section class="drawer-section section-errors">
        <h3 class="section-title">Errors</h3>
        ${errors.length > 0
          ? `<ul class="error-list">${errors.map(e => `
            <li class="error-item">
              <code>${escapeHtml(e.message || e)}</code>
              ${e.count ? `<span class="error-count">x${e.count}</span>` : ''}
            </li>`).join('')}</ul>`
          : '<p class="section-empty">No errors</p>'
        }
      </section>
    `);

    // Git section
    const git = sandbox.git || {};
    sections.push(`
      <section class="drawer-section section-git">
        <h3 class="section-title">Git</h3>
        ${git.branch ? `<p><strong>Branch:</strong> ${escapeHtml(git.branch)}</p>` : ''}
        ${git.commit ? `<p><strong>Commit:</strong> <code>${escapeHtml(git.commit)}</code></p>` : ''}
        ${git.status ? `<pre class="git-status">${escapeHtml(git.status)}</pre>` : ''}
        ${!git.branch && !git.commit ? '<p class="section-empty">No git info</p>' : ''}
      </section>
    `);

    // Timeline section
    sections.push(`
      <section class="drawer-section section-timeline">
        <h3 class="section-title">Timeline</h3>
        <div class="timeline-wrapper">
          ${timeline.length > 0 ? renderTimeline(timeline) : '<p class="section-empty">No timeline events</p>'}
        </div>
      </section>
    `);

    return sections.join('');
  }

  function tokenBarClass(pct) {
    if (pct >= 80) return 'danger';
    if (pct >= 50) return 'warning';
    return '';
  }

  // Subscribe to selectedSandbox changes
  unsubscribe = subscribe((newState) => {
    const selected = newState.selectedSandbox;
    if (selected && selected !== currentSandbox) {
      openPanel(selected);
    } else if (!selected && currentSandbox) {
      closePanel();
    }
  });

  // Expose close for external use
  return {
    destroy: () => {
      closePanel();
      if (unsubscribe) unsubscribe();
      if (panelEl) {
        panelEl.remove();
        panelEl = null;
      }
      if (backdropEl) {
        backdropEl.remove();
        backdropEl = null;
      }
    },
    close: closePanel
  };
}
