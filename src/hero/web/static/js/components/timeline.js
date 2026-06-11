import { escapeHtml, escapeAttr, timeAgo } from '../utils/dom.js';

const EVENT_COLORS = {
  running: 'green',
  done: 'cyan',
  error: 'red',
  pending: 'yellow'
};

/**
 * Render a vertical timeline from an array of events.
 * @param {Array} events - Array of event objects with { status, message, timestamp, ... }
 * @returns {string} HTML string
 */
export function renderTimeline(events) {
  if (!events || !Array.isArray(events) || events.length === 0) {
    return '<div class="timeline-empty">No events</div>';
  }

  // Sort by timestamp ascending
  const sorted = [...events].sort((a, b) => {
    const ta = a.timestamp || a.ts || a.time || 0;
    const tb = b.timestamp || b.ts || b.time || 0;
    return ta - tb;
  });

  return `
    <div class="timeline" role="list" aria-label="Event timeline">
      ${sorted.map((event, idx) => renderEvent(event, idx, sorted.length)).join('')}
    </div>
  `;
}

function renderEvent(event, idx, total) {
  const status = event.status || 'pending';
  const color = EVENT_COLORS[status] || 'grey';
  const message = event.message || event.name || 'Event';
  const timestamp = event.timestamp || event.ts || event.time || null;
  const isLast = idx === total - 1;

  const timeStr = timestamp
    ? timeAgo(timestamp)
    : '';

  return `
    <div class="timeline-event" role="listitem" data-status="${escapeAttr(status)}">
      <div class="timeline-marker">
        <span class="timeline-dot status-${color}" aria-hidden="true"></span>
        ${!isLast ? '<span class="timeline-line" aria-hidden="true"></span>' : ''}
      </div>
      <div class="timeline-content">
        <div class="timeline-message">${escapeHtml(message)}</div>
        ${timeStr ? `<div class="timeline-time">${escapeHtml(timeStr)}</div>` : ''}
        ${event.detail ? `<div class="timeline-detail">${escapeHtml(event.detail)}</div>` : ''}
      </div>
    </div>
  `;
}
