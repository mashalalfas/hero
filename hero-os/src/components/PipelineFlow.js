/**
 * HERO OS — PipelineFlow Component
 * Horizontal animated pipeline: NAVIGATION → PRE-COMMIT → BUILD → HARDEN → LEGAL → CI/PR → VERIFY → ARCHIVE
 * Status-colored nodes with glow effects, animated connectors, click-to-detail.
 */

import { getStore } from '../services/state.js';

// Pipeline stage definitions from pipeline.json (execute group)
const PIPELINE_STAGES = [
  { id: 'navigate',   label: 'NAVIGATION',  subtitle: 'graphify + hero map',  role: 'archivist' },
  { id: 'precommit',  label: 'PRE-COMMIT',  subtitle: 'Secrets · lint',       role: 'soldier' },
  { id: 'build',      label: 'BUILD',       subtitle: 'Compile · obfuscate',  role: 'soldier' },
  { id: 'harden',     label: 'HARDEN',      subtitle: 'Trivy CVE · secrets',  role: 'soldier' },
  { id: 'legal',      label: 'LEGAL',       subtitle: 'License · SBOM',       role: 'soldier' },
  { id: 'cipr',       label: 'CI/PR',       subtitle: 'Tests · build artifact', role: 'soldier' },
  { id: 'verify',     label: 'VERIFY',      subtitle: 'Composite gate',       role: 'verifier' },
  { id: 'archive',    label: 'ARCHIVE',     subtitle: 'Journal + memory',     role: 'archivist' },
];

const STAGE_ICONS = {
  navigate: '🧭', precommit: '🔒', build: '🔨',
  harden: '🛡️', legal: '⚖️', cipr: '🔀',
  verify: '✅', archive: '📦',
};

const STATUS_ORDER = ['idle', 'running', 'done', 'error', 'bypassed'];

let _container = null;
let _unsub = null;
let _currentData = [];

function mount(selector) {
  _container = document.querySelector(selector);
  if (!_container) return;
  render(_currentData);

  // Subscribe to sandbox tree changes to infer pipeline status
  const store = getStore('tree');
  if (store) {
    _unsub = store.subscribe((state) => {
      _currentData = state.trees || [];
      render(_currentData);
    });
  }
}

function unmount() {
  if (_unsub) { _unsub(); _unsub = null; }
  _container = null;
}

function render(trees) {
  if (!_container) return;

  // Aggregate stage statuses across all sandboxes
  const stageStatuses = _aggregateStageStatuses(trees);

  const wrapper = document.createElement('div');
  wrapper.className = 'pipeline-flow' + (stageStatuses.some(s => s === 'running') ? ' running' : '');

  PIPELINE_STAGES.forEach((stage, idx) => {
    const status = stageStatuses[idx] || 'idle';
    const isLast = idx === PIPELINE_STAGES.length - 1;

    // Node
    const node = document.createElement('div');
    node.className = `pipeline-stage`;

    const nodeInner = document.createElement('div');
    nodeInner.className = `stage-node ${status}`;
    nodeInner.dataset.stage = stage.id;
    nodeInner.title = `${stage.label}: ${stage.subtitle}`;
    nodeInner.innerHTML = `
      <span class="stage-icon">${STAGE_ICONS[stage.id] || '•'}</span>
      <span class="stage-name">${stage.label}</span>
      <span class="stage-status ${status}">${status}</span>
    `;
    nodeInner.addEventListener('click', () => _showStageDetail(stage, status, trees));
    node.appendChild(nodeInner);
    wrapper.appendChild(node);

    // Connector
    if (!isLast) {
      const conn = document.createElement('div');
      conn.className = `stage-connector${status === 'running' ? ' active' : ''}`;
      conn.innerHTML = '<span>▶</span>';
      wrapper.appendChild(conn);
    }
  });

  _container.innerHTML = '';
  _container.appendChild(wrapper);
}

function _aggregateStageStatuses(trees) {
  // For each pipeline stage, look across all sandboxes for the "worst" status
  // Priority: running > error > done > idle
  // We map from tree data by looking at the role/status
  const roleToStage = {
    archivist: 'navigate',
    soldier: 'precommit', // simplified mapping
    verifier: 'verify',
  };

  // Better: derive from sandbox status + dispatch files
  // If any sandbox is active, mark early stages as done/running
  // For a robust UI, we'll use the first active sandbox's implied progress

  const statuses = new Array(PIPELINE_STAGES.length).fill('idle');

  if (!trees.length) return statuses;

  // Find the most active sandbox
  const active = trees.find(t => ['active', 'running', 'working', 'spawning'].includes((t.status || '').toLowerCase()));
  const target = active || trees[0];
  const sbStatus = (target.status || 'idle').toLowerCase();

  if (sbStatus === 'idle') return statuses;

  // Derive pipeline progress from sandbox status heuristics
  const progress = _deriveProgress(target);

  PIPELINE_STAGES.forEach((stage, idx) => {
    if (idx < progress.completed) {
      statuses[idx] = 'done';
    } else if (idx === progress.current) {
      statuses[idx] = progress.isError ? 'error' : 'running';
    } else {
      statuses[idx] = 'idle';
    }
  });

  return statuses;
}

function _deriveProgress(treeItem) {
  // Walk the tree to find which stages are done/running
  const tree = treeItem.tree || {};
  const walk = (node) => {
    const results = [];
    if (!node) return results;
    const st = (node.status || 'idle').toLowerCase();
    const role = (node.role || '').toUpperCase();
    results.push({ role, status: st });
    (node.children || []).forEach(c => results.push(...walk(c)));
    return results;
  };

  const all = walk(tree);
  const hasError = all.some(n => ['error', 'failed', 'timeout'].includes(n.status));

  // Map roles to pipeline indices
  const roleIndex = {
    'SOLDIER': 2, // build-ish area
    'VERIFY': 6,
    'ARCH': 1,
    'LEAD': 1,
  };

  // If tree has children (soldiers), some execution is happening
  let completed = 0;
  if (tree.children && tree.children.length) {
    // lead spawned -> navigate/precommit done conceptually
    completed = 2;
    const childStatuses = tree.children.flatMap(c => walk(c)).map(n => n.status);
    if (childStatuses.some(s => ['done', 'completed', 'success'].includes(s))) completed = 4;
    if (childStatuses.every(s => ['done', 'completed', 'success'].includes(s))) completed = 6;
  }

  if (['done', 'completed', 'success', 'idle'].includes((treeItem.status || '').toLowerCase()) && completed < 6) {
    completed = 8; // all done
  }

  const current = completed < 8 ? completed : -1;
  return { completed, current: current >= 0 ? current : -1, isError: hasError };
}

function _showStageDetail(stage, status, trees) {
  const ui = getStore('ui');
  if (!ui) return;

  let body = `Stage: ${stage.label}\nStatus: ${status.toUpperCase()}\nRole: ${stage.role}\n\n`;

  // Show which sandboxes touched this stage
  trees.forEach(t => {
    body += `• ${t.sandbox} (${t.status || 'idle'})\n`;
  });

  ui.set({
    modalOpen: true,
    modalTitle: `${STAGE_ICONS[stage.id] || '•'} ${stage.label}`,
    modalBody: body,
  });
}

export const PipelineFlow = { mount, unmount, render };
