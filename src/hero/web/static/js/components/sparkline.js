/**
 * Zero-dependency SVG sparkline component.
 * Renders an inline SVG sparkline with gradient fill.
 */

/**
 * Render or update a sparkline in the given container.
 * @param {HTMLElement} container - DOM element to mount into
 * @param {number[]} data - Array of y-values
 * @param {Object} [options]
 * @param {number} [options.width=120] - SVG width
 * @param {number} [options.height=32] - SVG height
 * @param {string} [options.strokeColor] - CSS var or color for stroke (default: var(--accent))
 * @param {string} [options.fillColor] - CSS var for gradient stop (default: var(--accent))
 * @param {number} [options.strokeWidth=1.5]
 */
export function renderSparkline(container, data, options = {}) {
  if (!container) return;

  const {
    width = 120,
    height = 32,
    strokeColor = null,
    fillColor = null,
    strokeWidth = 1.5
  } = options;

  const effectiveStroke = strokeColor || 'var(--accent)';
  const effectiveFill = fillColor || 'var(--accent)';

  if (!data || data.length < 2) {
    // Render empty placeholder
    const existing = container.querySelector('.sparkline-svg');
    if (existing) existing.remove();
    return;
  }

  const padding = 2;
  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((val, i) => {
    const x = padding + (i / (data.length - 1)) * innerW;
    const y = padding + innerH - ((val - min) / range) * innerH;
    return { x, y };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  // Area fill path (close back to baseline)
  const firstX = points[0].x;
  const lastX = points[points.length - 1].x;
  const baseline = padding + innerH;
  const areaD = `${pathD} L${lastX.toFixed(1)},${baseline.toFixed(1)} L${firstX.toFixed(1)},${baseline.toFixed(1)} Z`;

  const gradientId = `spark-grad-${uniqueId()}`;

  const svg = `
    <svg class="sparkline-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <defs>
        <linearGradient id="${gradientId}" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="${effectiveFill}" stop-opacity="0.4" />
          <stop offset="100%" stop-color="${effectiveFill}" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <path d="${areaD}" fill="url(#${gradientId})" />
      <path d="${pathD}" fill="none" stroke="${effectiveStroke}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `;

  const existing = container.querySelector('.sparkline-svg');
  if (existing) {
    // Update in place: replace SVG entirely (cleaner than patching d attr since gradient changes)
    existing.outerHTML = svg;
  } else {
    container.insertAdjacentHTML('beforeend', svg);
  }
}

let _uid = 0;
function uniqueId() {
  return `_${++_uid}_${Date.now().toString(36)}`;
}
