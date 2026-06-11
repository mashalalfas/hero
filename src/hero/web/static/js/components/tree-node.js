import { escapeHtml, escapeAttr } from '../utils/dom.js';

// SVG inline icons for roles (no emoji — per UI/UX skill)
const ROLE_ICONS = {
  COMM:    '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.3"/><path d="M7 4v3l2 2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  LEAD:    '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1l2.5 5 5.5.8-4 3.9.9 5.5L7 13.5 2.1 16.2l1-5.5-4-3.9L4.5 6z" stroke="currentColor" stroke-width="1.3" transform="scale(0.7) translate(3,1)"/></svg>',
  ARCH:    '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M5 2v10M9 2v10M2 5h10M2 9h10" stroke="currentColor" stroke-width="0.8" opacity="0.4"/></svg>',
  SOLDIER: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="4" r="2.5" stroke="currentColor" stroke-width="1.3"/><path d="M7 7c-3 0-5 2-5 4h10c0-2-2-4-5-4z" stroke="currentColor" stroke-width="1.3"/></svg>',
  VERIFY:  '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

const DEFAULT_ICON = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.3" stroke-dasharray="2 2"/></svg>';

const STATUS_DOT_CLASSES = {
  active: 'active', running: 'active', working: 'active',
  idle: 'idle', dead: 'idle',
  error: 'error', failed: 'error',
  pending: 'pending', queued: 'pending', dispatched: 'pending',
  spawning: 'spawning',
  done: 'done', completed: 'done', success: 'done',
};

function getDotClass(status) {
  return STATUS_DOT_CLASSES[status] || 'idle';
}

export function renderTreeNode(node, depth = 0) {
  if (!node) return '';
  // Skip null/empty nodes
  if (!node.role && !node.label && !node.name) return '';

  const indent = depth * 20;
  const role = node.role || '';
  const label = node.label || node.name || 'Node';
  const status = node.status || 'idle';
  const model = node.model || '';
  const task = node.task || '';
  const color = node.color || '';

  const iconHtml = ROLE_ICONS[role] || DEFAULT_ICON;
  const dotClass = getDotClass(status);
  const statusColor = color || `var(--text-secondary)`;

  const children = (node.children && Array.isArray(node.children))
    ? node.children.map(child => renderTreeNode(child, depth + 1)).join('')
    : '';

  return `
    <div class="tree-node" style="--depth: ${depth};">
      <div class="tree-node-row" style="padding-left: ${indent + 8}px;">
        <span class="tree-node-icon" style="color: ${statusColor}">${iconHtml}</span>
        <span class="status-dot ${dotClass}"></span>
        <span class="tree-node-name">${escapeHtml(label)}</span>
        ${model ? `<span class="tree-node-model">${escapeHtml(model)}</span>` : ''}
        ${task ? `<span class="tree-node-task">${escapeHtml(task)}</span>` : ''}
      </div>
      ${children ? `<div class="tree-children">${children}</div>` : ''}
    </div>
  `;
}

export function renderTree(tree) {
  if (!tree) return '';
  return renderTreeNode(tree, 0);
}
