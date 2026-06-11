# SOLDIER BRIEF 5 — Mobile Responsive

## TASK
Ensure all HERO Viewport components work perfectly on mobile devices (375px+) with proper touch targets, responsive bento grid, and collapsible sections.

## FILES TO MODIFY
- `/home/max/Development/HERO/src/hero/web/static/css/layout.css` — Responsive breakpoints
- `/home/max/Development/HERO/src/hero/web/static/css/components.css` — Touch targets, mobile sizing
- `/home/max/Development/HERO/src/hero/web/static/css/base.css` — Mobile typography

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/js/components/mobile-nav.js` — Mobile navigation

## SPEC

### layout.css — Responsive Bento Grid

Add/modify breakpoints:

```css
/* ── Mobile-first responsive ── */

/* Base: single column for small screens */
.bento-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-3);
  padding: var(--space-3);
}

/* Tablet (≥768px): 2-column */
@media (min-width: 768px) {
  .bento-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
    padding: var(--space-4);
  }
  .tile-hero { grid-column: span 2; }
}

/* Desktop (≥1024px): 4-column */
@media (min-width: 1024px) {
  .bento-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-4);
  }
  .tile-hero { grid-column: span 2; grid-row: span 2; }
  .tile-metric { grid-column: span 1; }
  .tile-chart { grid-column: span 2; grid-row: span 2; }
}

/* Wide (≥1400px): full 12-column */
@media (min-width: 1400px) {
  .bento-grid {
    grid-template-columns: repeat(12, 1fr);
  }
  .tile-hero { grid-column: span 6; grid-row: span 2; }
  .tile-metric { grid-column: span 3; }
  .tile-chart { grid-column: span 4; grid-row: span 2; }
  .tile-accent { grid-column: span 2; }
}
```

### components.css — Touch Targets

```css
/* ── Touch-friendly sizing ── */

/* Minimum 44px touch targets */
.btn,
.badge,
.tree-sandbox-header,
.drawer-close,
.modal-close,
.control-btn {
  min-height: 44px;
  min-width: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Mobile padding adjustments */
@media (max-width: 767px) {
  .card {
    padding: var(--space-3);
  }

  .stat-pill {
    padding: var(--space-2) var(--space-3);
  }

  .drawer-panel {
    width: 100%;
    max-width: none;
  }

  .modal {
    width: calc(100% - var(--space-4));
    max-width: none;
    margin: var(--space-2);
  }

  /* Stack tree nodes vertically on mobile */
  .tree-node {
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .tree-task {
    max-width: 200px;
  }

  /* Search bar full width */
  .search-bar {
    flex-direction: column;
  }

  .search-bar input,
  .search-bar select {
    width: 100%;
  }
}
```

### base.css — Mobile Typography

```css
@media (max-width: 767px) {
  body {
    font-size: 13px;
    line-height: 1.4;
  }

  h1, .heading-1 {
    font-size: var(--text-xl);
  }

  h2, .heading-2 {
    font-size: var(--text-lg);
  }

  /* Prevent text selection on interactive elements */
  .btn, .badge, .tree-sandbox-header {
    user-select: none;
    -webkit-user-select: none;
  }

  /* Safe area insets for notched devices */
  .header {
    padding-top: max(var(--space-3), env(safe-area-inset-top));
  }

  .status-bar {
    padding-bottom: max(var(--space-2), env(safe-area-inset-bottom));
  }
}
```

### mobile-nav.js — Mobile Navigation

```javascript
// Mobile-specific navigation component
// - Hamburger menu for header actions
// - Swipe gestures for drawer open/close
// - Collapsible sections in detail panel

export function initMobileNav() {
  // Only activate on mobile viewports
  if (window.innerWidth > 767) return;

  // Add swipe-to-close for drawer
  setupDrawerSwipe();

  // Make sandbox cards collapsible
  setupCollapsibleCards();
}

function setupDrawerSwipe() {
  const drawer = document.querySelector('.drawer-panel');
  if (!drawer) return;

  let startX = 0;
  let currentX = 0;

  drawer.addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
  }, { passive: true });

  drawer.addEventListener('touchmove', (e) => {
    currentX = e.touches[0].clientX;
    const diff = currentX - startX;
    if (diff > 0) {
      drawer.style.transform = `translateX(${diff}px)`;
    }
  }, { passive: true });

  drawer.addEventListener('touchend', () => {
    const diff = currentX - startX;
    if (diff > 100) {
      // Swipe right → close
      closeDrawer();
    } else {
      drawer.style.transform = '';
    }
    startX = 0;
    currentX = 0;
  });
}

function setupCollapsibleCards() {
  // On mobile, tap header to expand/collapse tree
  document.addEventListener('click', (e) => {
    const header = e.target.closest('.tree-sandbox-header');
    if (!header) return;

    const card = header.closest('.tree-sandbox');
    if (card) {
      card.classList.toggle('expanded');
    }
  });
}
```

## DESIGN
- **Touch targets:** Minimum 44×44px for all interactive elements
- **Spacing:** Reduce padding on mobile (12px vs 16-24px)
- **Typography:** Slightly smaller on mobile (13px base vs 14px)
- **Safe areas:** Use `env(safe-area-inset-*)` for notched devices
- **Drawer:** Full-width on mobile, swipe-to-close gesture
- **Grid:** Single column on phone, 2-col tablet, 4-col desktop, 12-col wide

## CONSTRAINTS
- No JavaScript layout calculations — CSS handles all responsive behavior
- Touch events use `{ passive: true }` for scroll performance
- No hover-dependent interactions (hover is enhancement, not requirement)
- Drawer swipe only on mobile (check window.innerWidth)
- All breakpoints match layout.css values exactly
- Performance: no layout thrashing, use CSS transforms for animations

## ACCEPTANCE
1. Dashboard renders correctly at 375px, 768px, 1024px, 1400px widths
2. All buttons/links have ≥44px touch target
3. Bento grid: 1-col phone → 2-col tablet → 4-col desktop → 12-col wide
4. Drawer is full-width on mobile with swipe-to-close
5. Safe area insets applied on notched devices
6. No horizontal overflow at any breakpoint
7. Tree nodes wrap properly on narrow screens
8. Search bar stacks vertically on mobile
9. Typography scales down appropriately on mobile
10. No JavaScript-dependent layout (CSS-only responsive)
