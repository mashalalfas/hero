# SOLDIER BRIEF 6 — Futuristic Polish (Glassmorphism + Effects)

## TASK
Add Cyber-Glass visual effects: glassmorphism, glow effects, animation system, particle system, and font integration (Orbitron + Share Tech Mono).

## FILES TO CREATE
- `/home/max/Development/HERO/src/hero/web/static/js/components/effects.js` — Particle system + glow effects

## FILES TO MODIFY
- `/home/max/Development/HERO/src/hero/web/static/css/tokens.css` — Add effect tokens
- `/home/max/Development/HERO/src/hero/web/static/css/animations.css` — Add advanced keyframes
- `/home/max/Development/HERO/src/hero/web/static/css/components.css` — Glassmorphism on all components
- `/home/max/Development/HERO/src/hero/web/static/index.html` — Font imports

## SPEC

### Font Integration (index.html)

Add to `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
```

### tokens.css — Add Effect Tokens

```css
/* ── Glow Effects ── */
--glow-accent: 0 0 10px rgba(0, 240, 255, 0.3), 0 0 30px rgba(0, 240, 255, 0.1);
--glow-accent-strong: 0 0 15px rgba(0, 240, 255, 0.5), 0 0 40px rgba(0, 240, 255, 0.2);
--glow-success: 0 0 10px rgba(0, 255, 136, 0.3), 0 0 30px rgba(0, 255, 136, 0.1);
--glow-danger: 0 0 10px rgba(255, 0, 60, 0.3), 0 0 30px rgba(255, 0, 60, 0.1);
--glow-warning: 0 0 10px rgba(255, 170, 0, 0.3);

/* ── Scanline ── */
--scanline-opacity: 0.03;
--scanline-speed: 8s;

/* ── Noise texture (CSS only) ── */
--noise-opacity: 0.015;

/* ── Particle ── */
--particle-size: 2px;
--particle-color: var(--color-accent);
--particle-speed: 15s;
```

### animations.css — Advanced Keyframes

```css
/* ── Glow pulse ── */
@keyframes glowPulse {
  0%, 100% { box-shadow: var(--glow-accent); }
  50% { box-shadow: var(--glow-accent-strong); }
}

/* ── Scanline sweep ── */
@keyframes scanline {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100vh); }
}

/* ── Gradient shift (background animation) ── */
@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

/* ── Typing cursor ── */
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── Float (subtle Y movement) ── */
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

/* ── Shake (error feedback) ── */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
  20%, 40%, 60%, 80% { transform: translateX(2px); }
}

/* ── Utility classes ── */
.glow-accent { box-shadow: var(--glow-accent); }
.glow-success { box-shadow: var(--glow-success); }
.glow-danger { box-shadow: var(--glow-danger); }
.animate-glow { animation: glowPulse 2s ease-in-out infinite; }
.animate-float { animation: float 3s ease-in-out infinite; }
.animate-shake { animation: shake 0.5s ease-in-out; }
```

### components.css — Glassmorphism

Apply glass effect to all major surfaces:

```css
/* ── Glass Card ── */
.card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
}

.card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-glow-sm);
}

/* ── Glass Header ── */
.header {
  background: rgba(10, 10, 15, 0.9);
  backdrop-filter: blur(var(--glass-blur-heavy));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy));
  border-bottom: 1px solid var(--glass-border);
}

/* ── Glass Drawer ── */
.drawer-panel {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur-heavy));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy));
  border-left: 1px solid var(--glass-border);
}

/* ── Glass Modal ── */
.modal {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur-heavy));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy));
  border: 1px solid var(--glass-border);
}

.modal-overlay {
  background: rgba(5, 5, 8, 0.8);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

/* ── Glass Toast ── */
.toast {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
}

/* ── Scanline overlay (optional cyber effect) ── */
.scanline-overlay::after {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 240, 255, var(--scanline-opacity)) 2px,
    rgba(0, 240, 255, var(--scanline-opacity)) 4px
  );
  pointer-events: none;
  z-index: 9999;
  animation: scanline var(--scanline-speed) linear infinite;
}

/* ── Noise texture overlay ── */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  opacity: var(--noise-opacity);
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 9998;
}

/* ── Status dot glow ── */
.tree-dot.active {
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success), 0 0 12px rgba(0, 255, 136, 0.3);
}

.tree-dot.error {
  background: var(--color-danger);
  box-shadow: 0 0 6px var(--color-danger), 0 0 12px rgba(255, 0, 60, 0.3);
}

/* ── Accent border glow on focus ── */
*:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  box-shadow: var(--glow-accent);
}
```

### effects.js — Particle System

```javascript
// Cyberpunk particle system — floating dots in background
// Lightweight: ≤30 particles, CSS animations only (no requestAnimationFrame)

export function initParticles(container, options = {}) {
  const {
    count = 20,
    color = 'var(--color-accent)',
    maxSize = 3,
    speed = 15,
    opacity = 0.3
  } = options;

  const canvas = document.createElement('div');
  canvas.className = 'particle-canvas';
  canvas.style.cssText = `
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
  `;

  for (let i = 0; i < count; i++) {
    const particle = document.createElement('div');
    const size = Math.random() * maxSize + 1;
    const x = Math.random() * 100;
    const duration = speed + Math.random() * 10;
    const delay = Math.random() * duration;

    particle.style.cssText = `
      position: absolute;
      width: ${size}px;
      height: ${size}px;
      background: ${color};
      border-radius: 50%;
      left: ${x}%;
      bottom: -10px;
      opacity: ${opacity * (Math.random() * 0.5 + 0.5)};
      animation: particleRise ${duration}s ${delay}s linear infinite;
    `;
    canvas.appendChild(particle);
  }

  // Add keyframes if not exists
  if (!document.getElementById('particle-keyframes')) {
    const style = document.createElement('style');
    style.id = 'particle-keyframes';
    style.textContent = `
      @keyframes particleRise {
        0% {
          transform: translateY(0) translateX(0);
          opacity: 0;
        }
        10% { opacity: var(--particle-opacity, 0.3); }
        90% { opacity: var(--particle-opacity, 0.3); }
        100% {
          transform: translateY(-100vh) translateX(${Math.random() > 0.5 ? '' : '-'}${Math.random() * 40 + 10}px);
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }

  container.appendChild(canvas);
  return {
    destroy: () => canvas.remove()
  };
}

// Glow effect: adds pulsing box-shadow to element
export function addGlow(element, color = 'accent', intensity = 'normal') {
  const cls = `glow-${color}${intensity === 'strong' ? '-strong' : ''}`;
  element.classList.add(cls);
  return { remove: () => element.classList.remove(cls) };
}
```

## DESIGN
- **Glassmorphism:** Every surface uses `backdrop-filter: blur()` with semi-transparent bg
- **Glow:** Status dots pulse with matching color glow. Active elements get accent glow on focus
- **Particles:** Subtle floating cyan dots in background, ≤30 count, slow rise animation
- **Scanline:** Optional ultra-subtle horizontal line sweep (toggle via `.scanline-overlay` class)
- **Noise:** Ultra-subtle SVG noise texture on body (1.5% opacity)
- **Fonts:** Orbitron for all headings/labels, Share Tech Mono for data/code/mono, Inter for body text
- **Transitions:** Everything transitions border-color and box-shadow on hover (300ms)

## CONSTRAINTS
- Performance: particles use CSS animation only, no JS animation loop
- `backdrop-filter` has fallback: solid bg for browsers that don't support it
- Scanline and noise are optional (class-toggled), not always-on
- Font loading: use `display=swap` to prevent FOIT
- No heavy libraries — all effects are pure CSS + vanilla JS
- Glow effects use box-shadow, not filter (better performance)

## ACCEPTANCE
1. Orbitron font loads for headings, Share Tech Mono for data
2. All cards, drawer, modal, toast have glassmorphism (backdrop-filter blur)
3. Status dots have color-matched glow effect
4. Focus-visible elements show cyan outline with glow
5. Particle system renders ≤30 floating dots in background
6. Scanline overlay available via `.scanline-overlay` class
7. Noise texture on body at ≤2% opacity
8. All effects have CSS fallbacks for unsupported browsers
9. No performance degradation (check with DevTools Performance tab)
10. Effects are toggleable (can disable particles/scanline via class)
