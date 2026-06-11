# SOLDIER BRIEF 1 — Design System

## TASK
Create the complete CSS design system for HERO Viewport v3 Cyber-Glass theme.

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/css/tokens.css`
- `/home/max/Development/HERO/src/hero/web/static/css/base.css`
- `/home/max/Development/HERO/src/hero/web/static/css/layout.css`
- `/home/max/Development/HERO/src/hero/web/static/css/components.css`
- `/home/max/Development/HERO/src/hero/web/static/css/animations.css`

## SPEC

### tokens.css — Design Tokens
All custom properties. Single source of truth.

```css
:root {
  /* ── Midnight Command Palette ── */
  --color-bg-deepest:    #050508;
  --color-bg-primary:    #0a0a0f;
  --color-bg-surface:    #0f0f18;
  --color-bg-elevated:   #141420;
  --color-bg-hover:      #1a1a2e;

  /* ── Glass ── */
  --glass-bg:            rgba(14, 14, 24, 0.75);
  --glass-border:        rgba(0, 240, 255, 0.08);
  --glass-blur:          12px;
  --glass-blur-heavy:    20px;

  /* ── Accents ── */
  --color-accent:        #00f0ff;  /* Cyan primary */
  --color-accent-dim:    rgba(0, 240, 255, 0.15);
  --color-accent-glow:   rgba(0, 240, 255, 0.4);
  --color-success:       #00ff88;
  --color-success-dim:   rgba(0, 255, 136, 0.12);
  --color-danger:        #ff003c;
  --color-danger-dim:    rgba(255, 0, 60, 0.12);
  --color-warning:       #ffaa00;
  --color-warning-dim:   rgba(255, 170, 0, 0.12);
  --color-info:          #6366f1;
  --color-info-dim:      rgba(99, 102, 241, 0.12);

  /* ── Text ── */
  --text-primary:        #e8eaed;
  --text-secondary:      #8b8fa3;
  --text-tertiary:       #5a5e73;
  --text-accent:         var(--color-accent);

  /* ── Borders ── */
  --border-subtle:       rgba(255, 255, 255, 0.04);
  --border-default:      rgba(255, 255, 255, 0.08);
  --border-hover:        rgba(0, 240, 255, 0.2);
  --border-active:       rgba(0, 240, 255, 0.4);

  /* ── Spacing (4px base) ── */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 20px; --space-6: 24px;
  --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* ── Radius ── */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --radius-full: 9999px;

  /* ── Typography ── */
  --font-display: 'Orbitron', sans-serif;
  --font-mono: 'Share Tech Mono', 'JetBrains Mono', monospace;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;

  --text-xs: 11px;  --text-sm: 12px;  --text-base: 14px;
  --text-lg: 16px;  --text-xl: 20px;  --text-2xl: 24px;
  --text-3xl: 32px;

  /* ── Shadows ── */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.5);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.6);
  --shadow-glow: 0 0 20px var(--color-accent-glow);
  --shadow-glow-sm: 0 0 8px var(--color-accent-glow);

  /* ── Animation ── */
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
  --ease-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);

  /* ── Z-Index ── */
  --z-base: 1;
  --z-card: 10;
  --z-header: 100;
  --z-drawer: 200;
  --z-modal: 300;
  --z-toast: 400;
}
```

### base.css — Reset + Typography
- Box-sizing border-box reset
- Body: `var(--color-bg-primary)`, `var(--font-body)`, antialiased
- Headings: `var(--font-display)`, uppercase, letter-spacing 0.05em
- Code/mono: `var(--font-mono)`
- Selection: `var(--color-accent-dim)` background
- Scrollbar: thin, dark track, `var(--color-accent)` thumb on hover
- Focus-visible: `var(--color-accent)` outline, 2px offset
- Links: `var(--color-accent)`, no underline by default

### layout.css — Bento Grid System
- 12-column CSS Grid
- `.bento-grid`: `grid-template-columns: repeat(12, 1fr)`, gap 16px
- Tile spans: `.tile-hero { grid-column: span 6; grid-row: span 2; }`
  `.tile-metric { grid-column: span 3; }`
  `.tile-chart { grid-column: span 4; grid-row: span 2; }`
  `.tile-accent { grid-column: span 2; }`
- Container: max-width 1400px, centered, padding 24px
- Responsive breakpoints:
  - ≤1024px: hero→span 8, metric→span 4, chart→span 6
  - ≤768px: everything→span 12, single column
  - ≤480px: reduce padding to 12px

### components.css — All UI Components
- `.card`: glass background, backdrop-filter blur, subtle border, hover glow
- `.badge` variants: `.badge-active` (green), `.badge-idle` (grey), `.badge-error` (red), `.badge-pending` (yellow)
- `.stat-pill`: compact stat with label + value + sub
- `.progress-bar`: animated fill with gradient
- `.tree-node`: indented tree lines with connector characters
- `.drawer`: slide-in panel from right, glass background
- `.modal`: centered overlay with glass panel
- `.toast`: bottom-right notification, auto-dismiss
- `.btn` variants: `.btn-primary` (accent), `.btn-danger` (red), `.btn-ghost` (transparent)
- `.btn-kill`: danger button with skull icon, confirmation state
- `.search-bar`: glass input with icon
- `.model-badge`: purple accent for model names
- `.timeline`: vertical timeline with dot indicators
- `.empty-state`: centered placeholder with icon

### animations.css — Keyframes + Transitions
- `@keyframes fadeIn`: opacity 0→1
- `@keyframes slideUp`: translateY(10px)→0 + fade
- `@keyframes slideInRight`: translateX(100%)→0 (drawer)
- `@keyframes pulse`: opacity 1→0.5→1 (live indicator)
- `@keyframes glow`: box-shadow pulse with accent color
- `@keyframes shimmer`: gradient sweep (loading skeleton)
- `@keyframes scanline`: horizontal line sweep (cyber effect)
- `.animate-fade-in`, `.animate-slide-up`: utility classes
- `.transition-all`: all properties, var(--duration-normal), var(--ease-out)

## DESIGN
- **Palette:** Midnight Command — deep blacks (#0a0a0f), cyan accent (#00f0ff), red danger (#ff003c), green success (#00ff88)
- **Glass:** `background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur)); border: 1px solid var(--glass-border);`
- **Spacing:** 4px grid. Consistent padding: cards 16-20px, sections 24-32px
- **Borders:** Very subtle — 4-8% white opacity. Glow on hover/active

## CONSTRAINTS
- Pure CSS, no preprocessor, no build step
- All values via CSS custom properties (tokens.css)
- Mobile-first responsive where noted
- No `!important`
- Each file must work standalone (no circular deps)

## ACCEPTANCE
1. Create all 5 CSS files in `static/css/`
2. Each file has a clear header comment: `/* HERO Viewport — [filename] */`
3. tokens.css defines ≥40 custom properties
4. layout.css bento grid works: 12-col at 1400px, single-col at 375px
5. components.css covers: card, badge, button, drawer, modal, toast, tree, progress
6. animations.css has ≥6 keyframes + utility classes
7. All files import cleanly: `<link rel="stylesheet" href="/static/css/tokens.css">` etc.
