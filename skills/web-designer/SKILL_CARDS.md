# WEB DESIGN SKILL CARDS — HERO Soldier Kit

## Priority Index
P0 = essential for every web build
P1 = common enough to know
P2 = nice-to-have, research on demand

---

## Card: GSAP — Animation
- Type: P0
- Import: `gsap`, `gsap/ScrollTrigger`, `gsap/MotionPathPlugin`
- Key patterns:
  - `gsap.to(".el", { x: 100, duration: 0.8, ease: "power3.out" })` — basic tween
  - ScrollTrigger: `gsap.to(".el", { scrollTrigger: ".trigger", start: "top 80%", y: 0 })` — scrub-free, or `scrub: 1` for smooth tied-to-scroll
  - Timeline: `const tl = gsap.timeline(); tl.to(a).to(b, { stagger: 0.1 })` — sequenced + stagger
  - `clamp()` wrapper (v3.12+): `end: "clamp(top+=100, 0, maxScroll)"` — prevents animation leaking beyond page bounds
  - `gsap.matchMedia()` — responsive + `prefers-reduced-motion` friendly breakpoints
- Context budget: ~400 tokens
- Gotchas:
  - ScrollTrigger needs `ScrollTrigger.refresh()` after dynamic content / image load
  - `gsap.context()` for cleanup in React/Vue/Svelte (prevents memory leaks)
  - Core ~24KB gzipped; ScrollTrigger adds ~6KB. Bundle only plugins you import.
- Tiny example:
  ```js
  gsap.registerPlugin(ScrollTrigger)
  gsap.from(".card", {
    scrollTrigger: ".card", start: "top 80%",
    y: 60, opacity: 0, stagger: 0.15, duration: 0.8
  })
  ```

---

## Card: Three.js — 3D
- Type: P1
- Import: `three`, `three/examples/jsm/controls/OrbitControls`, `three/examples/jsm/loaders/GLTFLoader`
- Key patterns:
  - Scene: `const scene = new THREE.Scene(); const camera = new THREE.PerspectiveCamera(75, w/h, 0.1, 1000);`
  - Renderer: `new THREE.WebGLRenderer({ antialias: true, alpha: true })` — alpha for compositing over DOM
  - GLTF: `GLTFLoader.load(url, gltf => scene.add(gltf.scene))` — glTF is the runtime standard (fast, compact)
  - Scroll-based 3D: animate camera.position/rotation inside a `requestAnimationFrame` loop driven by scroll Y
  - Lighting: `AmbientLight` (base fill) + `DirectionalLight` (sun/shadows)
- Context budget: ~500 tokens
- Gotchas:
  - Three.js ES modules from `three/examples/jsm/` require bundler (not CDN-friendly without importmap)
  - `OrbitControls` auto-rotates on drag; disable with `controls.enableDamping = false` if unwanted
  - Memory: dispose geometries/materials/textures on component unmount
- Key helpers: `OrbitControls`, `GLTFLoader`, `DRACOLoader` (compressed models), `EffectComposer` (post-processing)

---

## Card: Scroll / Parallax Libraries
- Type: P1
- Import: `@studio-freight/lenis` (Lenis) | `locomotive-scroll` (v5 beta / v4 stable) | `aos` (AOS) | `gsap/ScrollTrigger` (preferred)
- Key patterns:
  - Lenis (modern default): `const lenis = new Lenis(); function raf(t) { lenis.raf(t); requestAnimationFrame(raf) } requestAnimationFrame(raf)` — smooth scroll with WebGL sync
  - ScrollTrigger scrub: `gsap.to(el, { scrollTrigger: { trigger, scrub: 1 }, y: -100 })` — replaces ScrollMagic for most use cases
  - AOS (CSS-only, zero-JS-animation): `data-aos="fade-up"` attributes — simple but inflexible
  - Native CSS parallax: `background-attachment: fixed` or `perspective()` + `translateZ()` trick (mobile buggy)
- Context budget: ~400 tokens
- Gotchas:
  - Locomotive Scroll v5 rewrote internals; v4 is still more battle-tested
  - Lenis conflicts with native `scroll-behavior: smooth` CSS; disable one
  - ScrollMagic is effectively unmaintained — migrate to GSAP ScrollTrigger
  - AOS doesn't play well with dynamically loaded content

---

## Card: UI Animation Libraries
- Type: P0
- Import:
  - React: `motion/react` (formerly Framer Motion — rebranded to "Motion" in 2024)
  - Vanilla: `motion` (Motion One — WAAPI wrapper)
  - Framework-agnostic: `animejs` (Anime.js v4)
- Key patterns:
  - Motion/React: `<motion.div animate={{ x: 100 }} transition={{ type: "spring" }} />` — prop-driven
  - Layout animations (Motion): `<motion.div layout />` — auto-animates position/size on reorder
  - Motion One (vanilla): `animate(".el", { x: 100 }, { duration: 0.4 })` — WAAPI-based, ~4KB
  - Anime.js: `anime({ targets: ".el", translateX: 100, delay: anime.stagger(50) })` — timeline-rich
- Context budget: ~400 tokens
- Gotchas:
  - Motion mini mode (WAAPI only) = 2.3KB; hybrid mode adds JS engine for sequences/motion values
  - Motion uses `motion/react` not `framer-motion` in latest versions (breaking rename)
  - Anime.js v4 has new modular ESM build; check version before importing
  - For non-React, prefer Motion One over full Motion bundle

---

## Card: Design Systems — CSS Styling
- Type: P0
- Import: `tailwindcss` (PostCSS plugin) | `styled-components` / `@emotion/styled` | CSS Modules (`.module.css`)
- Key patterns:
  - Tailwind: utility-first, JIT mode, `@apply` for component extraction, `tailwind.config.js` for theme tokens
  - Typography scale: `text-xs / text-sm / text-base / text-lg / text-xl / text-2xl / text-4xl` (Tailwind defaults)
  - Spacing: 4px base unit — `p-4` = 16px, `gap-6` = 24px; use `space-y-*` for vertical rhythm
  - Color: semantic tokens `bg-primary`, `text-muted`; map to HSL values in config for dark mode
  - CSS Modules: `styles.card` — scoped, zero-runtime, ideal for component libraries
- Context budget: ~400 tokens
- Gotchas:
  - Tailwind purge/content scan must include template literals and dynamic class strings
  - styled-components has SSR quirks; use `ServerStyleSheet` or Emotion SSR for Next.js
  - CSS Modules class names are hashed — inspect via dev tools to debug
  - Combining all three in one project is over-engineering; pick one primary approach

---

## Card: WebGL / Creative Coding
- Type: P2
- Import: `p5.js` (canvas 2D/WebGL) | `pixi.js` (2D WebGL sprites) | `three` (3D) | `babylonjs` (3D engine) | `regl` (functional WebGL)
- Key patterns:
  - p5.js: `setup()` + `draw()` loop — generative art, data viz, prototyping. Easy abstraction, slower for production
  - Pixi.js: `const app = new PIXI.Application(); sprite = PIXI.Sprite.from(texture)` — fastest 2D WebGL renderer; use for games, interactive graphics
  - Babylon.js: full 3D engine with physics, collisions, GUI, VR — steepest learning curve but most complete
  - regl: functional, declarative WebGL — minimal overhead, best for custom shaders with predictable data flow
- Context budget: ~450 tokens
- Gotchas:
  - p5.js in instance mode (not global) to avoid polluting scope
  - Pixi.js v8 has breaking API changes from v7 — verify version
  - Three.js for 2D sprites is overkill; use Pixi.js instead
  - WebGL context loss: add `webglcontextlost` / `webglcontextrestored` handlers for production

---

## Card: Responsive Design — Modern CSS
- Type: P0
- Import: (no library — native CSS)
- Key patterns:
  - Container queries: `@container (min-width: 400px) { .card { grid-template-columns: 1fr 1fr; } }` — respond to parent, not viewport
  - Fluid typography: `font-size: clamp(1rem, 2.5vw + 0.5rem, 2rem)` — min, preferred, max
  - Fluid spacing: `padding: clamp(1rem, 5vw, 4rem)` — scales with viewport naturally
  - Intrinsic grid: `grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr))` — no media query breakpoints
  - `min()` / `max()` math: `width: min(90vw, 1200px)` — cap at max without media queries
- Context budget: ~350 tokens
- Gotchas:
  - Container queries require `container-type: inline-size` on the parent
  - `clamp()` middle value is linear — use `min()` or custom properties for non-linear scales
  - Safari added container query support in v16; not a concern post-2023
  - `min()` and `max()` work in `<length>` contexts only, not all CSS properties

---

## Card: Accessibility — Animation & Color
- Type: P0
- Import: (native CSS/HTML — no library required)
- Key patterns:
  - `prefers-reduced-motion`: `@media (prefers-reduced-motion: reduce) { *, *::before { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`
  - In GSAP: `gsap.matchMedia()` — add reduced-motion variants that replace motion with fades
  - Color contrast: WCAG AA = 4.5:1 (normal text), 3:1 (large text). Tools: `axe DevTools`, `WebAIM Contrast Checker`
  - Focus management: trap focus in modals, return focus on close, use `focus-visible` outline
  - Semantic HTML first: `<button>` for actions, `<a>` for navigation — animation layer on top
- Context budget: ~350 tokens
- Gotchas:
  - `prefers-reduced-motion` is a browser/OS setting; don't override with a site toggle alone
  - Reducing animation to 0.01ms still triggers the animation event; consider `animation: none`
  - WCAG 2.3.3 (AAA) — essential animation is exempt; decorative animation must be removable
  - Focus indicators must not be removed — ever. Custom outlines OK if contrast ≥ 3:1

---

## Card: Performance — Animation & Loading
- Type: P0
- Import: (native CSS/JS patterns)
- Key patterns:
  - `will-change: transform, opacity` — hint to browser; REMOVE after animation ends (or keep short-lived)
  - CSS containment: `contain: layout paint` on animated containers — limits repaint scope
  - Bundle splitting: `import("gsap/ScrollTrigger")` dynamic import for scroll-heavy pages only
  - Lazy load libraries: `if (sectionRef) import("./animations.js").then(m => m.init())` — load on intersection
  - `content-visibility: auto` — skip rendering off-screen animated sections until scrolled near
- Context budget: ~350 tokens
- Gotchas:
  - `will-change` overuse causes memory pressure — limit to ≤ 3 elements per frame
  - `will-change` on `left`/`top` triggers layout; use `transform` instead (GPU-composited)
  - Dynamic import with GSAP means `ScrollTrigger` needs explicit `ScrollTrigger.refresh()` after load
  - `content-visibility` requires `contain-intrinsic-size` as fallback to prevent layout shift

---

*Compiled: 2026-06-18 | GSAP v3.15.0 | Three.js latest stable | Motion (Framer Motion) v11+ | Lenis v1.x*
