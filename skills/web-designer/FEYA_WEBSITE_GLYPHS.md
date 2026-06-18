# Feya PDF — Glyphs Direction

## Council: Revised 2026-06-18
### Replaces previous concepts ("The Highlight", "Paper & Pixel", "The Vault") — rejected as too animation-heavy

---

## Section 1: The Refined Concept

### Name: "The Glyph"

Feya PDF is not a tool. It is a **studio**. Every highlighted passage is a commissioned work. Every document is a project in the portfolio. The reader is the artist; the highlighter is the brush. The website presents Feya the way a design studio presents itself — through craft, restraint, and a single visual signature. That signature is **the glyph**: a minimal symbol that stands for "illumination" — a mark made on text. It appears once as the hero, once as a favicon, once as a subtle divider between sections. No logos. No mockups. No demos. Just type, space, and the glyph.

---

## Section 2: Page Layout

A single vertical scroll. Six sections. No navigation bar (a thin top bar with "Feya" in small caps and a subtle "Illuminate" text-link on the right fades in after the hero). Each section breathes. Nothing happens that doesn't need to.

---

### 1. Hero

**What it is:** One word. `Feya` in approximately 200px warm white weight 300. Centered. Sits alone on black. A single glyph — a horizontal line with a small diamond at the end, like a stylized highlighter tip — rests about 1.5x the font-size below the word, centered, small (60px wide). The only motion: a subtle low-opacity grain-texture overlay (CSS mask with an animated noise PNG, 2s loop) and, on desktop, a very soft vignette of warm light that follows the cursor at 10% opacity (JS pointer listener updating a radial-gradient CSS variable). That's it. No particles. No floating text. No entrance animation beyond a 1-second fade-in on page load.

**Copy:**
```
Feya

⎯◇    (the glyph)
```

**States:**
- Load: word fades up (opacity 0→1, y: 30px→0, 800ms ease-out)
- Idle: grain noise texture faintly pulses
- Mouse move: warmth follows cursor via radial-gradient at (mouseX, mouseY) — imperceptible unless you look for it
- Scroll: glyph fades out after 40vh; word remains centered until next section crosses it

---

### 2. Manifesto

**What it is:** Three lines of editorial copy. White type on black. Left-aligned but generously inset (40% left margin, like a pull quote in a book). Each line separated by a full line-height of space. A hairline horizontal rule (1px, 40% width) floats above the copy, 60px from the top of the section. The glyph reappears, tiny, at the end of the last line.

**Copy:**
```
A highlight is a thought made visible.
A document is a conversation with yourself.
Feya is the instrument.
                                                                     ⎯◇
```

**Scroll behavior:** Each line fades in + shifts letter-spacing from -0.05em to normal. First line triggers at section top entering viewport, second at 25%, third at 50%. Uses GSAP ScrollTrigger with a 400ms stagger.

---

### 3. The Works

**What it is:** A 3×2 grid of "project cards" — each representing a famous text with a Feya highlight. Each card is minimal: a number (01–06) in 12px light-gray weight 400, a title in 28px warm white weight 350, an author in 14px gray weight 300, a colored stripe (3px tall, 60px wide) in one of two accent colors (amber or rose), and a 3-word excerpt in italic 16px gray. Cards have no borders — just type and the stripe. On hover, the stripe widens to 100% width (300ms CSS transition), the title's letter-spacing tightens by 0.02em, and a subtle dark-gray card background appears at 5% opacity.

**The 6 cards:**

| # | Title | Author | Stripe | Excerpt |
|---|-------|--------|--------|---------|
| 01 | Moby-Dick | Herman Melville | Amber | "Call me Ishmael." |
| 02 | Romeo and Juliet | William Shakespeare | Rose | "Parting is sweet sorrow." |
| 03 | Leaves of Grass | Walt Whitman | Amber | "I celebrate myself." |
| 04 | The Great Gatsby | F. Scott Fitzgerald | Rose | "Gatsby believed in green light." |
| 05 | Pride and Prejudice | Jane Austen | Amber | "It is truth." |
| 06 | The Raven | Edgar Allan Poe | Rose | "Nevermore." |

**Copy:**
```
     01
     Moby-Dick
     Herman Melville
     ▬ (amber 3px stripe)
     "Call me Ishmael."
```

**Scroll behavior:** Cards stagger into view — 01 and 02 simultaneously, then 03 and 04, then 05 and 06. Each card fades up (opacity 0→1, y: 40px→0) and its number slides in from the left (x: -20px→0). GSAP ScrollTrigger, 200ms stagger per row.

---

### 4. Capabilities

**What it is:** Four columns. Each has: a tiny glyph variant (different orientation of the same diamond-line motif — diamond top, diamond bottom, diamond left, diamond right — rendered as 24px SVG inline), a headline in 22px warm white weight 350, and one line of 14px gray weight 300 copy. The columns are spaced evenly with generous gaps (at least 4rem between). The section has a thin top rule (full width, 1px dark gray at 30% opacity).

**Copy:**

| Glyph | Headline | Copy |
|-------|----------|------|
| ◇↑ | Read | Continuous scroll. Night mode. Every typeface preserved. |
| ◇↓ | Highlight | Precision stroke. Subtle glow. Your library of marginalia. |
| ◇← | Secure | Biometric lock. Encrypted at rest. Your documents, yours only. |
| ◇→ | Sync | Across devices. Offline-first. One library everywhere. |

**Scroll behavior:** Columns stagger in left-to-right. Each column fades up with a 150ms delay between them. No additional effects.

---

### 5. The Vault

**What it is:** A single dark section. The word "Secure" in 120px warm white weight 250, centered. Below it, a 48px SVG padlock glyph — minimal: a circle and a line (no shackle, just a circle with a vertical bar intersecting it). On scroll, the circle morphs into a checkmark (simple SVG path morph: the lock circle's path changes to a circle with a check inside). The transition is subtle, takes 600ms, scrubbed with ScrollTrigger. Below the lock, in 14px gray weight 300: "Biometric. Encrypted. Yours alone."

**Copy:**
```
Secure

◎→✓   (SVG morphs on scroll)
Biometric. Encrypted. Yours alone.
```

**Scroll behavior:** The word fades up. The lock morphs when the section is 40% visible, using GSAP ScrollTrigger scrub with SVG path interpolation. No tween beyond the path change. No glow. No particles.

---

### 6. Cross-Platform

**What it is:** Two lines of type. Centered. First line 28px warm white weight 300. Second line 14px gray weight 300 with the tiny glyph centered beneath. Full-width hairline rule above, full-width hairline rule below. This is the quietest section on the page.

**Copy:**
```
Phone. Tablet. Desktop.

One library.

     ⎯◇
```

**Scroll behavior:** Fade in, 500ms. Nothing fancy.

---

### 7. CTA

**What it is:** A single line of text — "Illuminate what matters" — centered, in 28px warm white weight 300 with an underline that draws in from center on hover. The underline is a bottom-border with a CSS pseudo-element that scalesX(0)→scaleX(1) on hover, using transform-origin: center. The glyph sits above it, 24px, centered, with a slow pulsing opacity (CSS keyframes, 4s loop, 0.4→0.7). Below the CTA, a thin footer: "Feya PDF © 2026" in 11px dark gray at 40% opacity.

**Copy:**
```
     ◇

Illuminate what matters

Feya PDF © 2026
```

**Hover effect:** Underline draws center-out (CSS: `::after { transform: scaleX(0); transition: transform 400ms ease; }` on hover `scaleX(1)`). No JavaScript needed.

---

## Section 3: Soldier Task Split

5 pieces, each ≤15K tokens, build-order sequential. Each piece produces a verifiably working HTML file (open in browser, see the section(s)).

### Piece 1: HTML skeleton + Hero + Core typography (Foundation)

**Dependency:** None
**What to build:**
- Single `index.html` with inline `<style>` and `<script>` blocks
- CSS reset, dark theme variables (see Section 4 palette), load fonts (Google Fonts: Inter for body, plus a display font such as "Playfair Display" for the hero/manifesto)
- GSAP from CDN (`<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js">`), ScrollTrigger plugin (`<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js">`)
- Lenis smooth scroll: `<script src="https://unpkg.com/lenis@1.1.18/dist/lenis.min.js">`
- **Hero section** exactly as described: `Feya` in 200px Playfair Display weight 300, centered, the glyph below, grain overlay (CSS mask with animated noise PNG from a data-URI), mouse-following warmth (JS pointer listener updating `--mouse-x`, `--mouse-y` CSS vars used in a `radial-gradient` on the hero div), 1s fade-in on load
- A thin top bar with "FEYA" in 11px letter-spaced 0.2em on the left and "Illuminate" in 11px on the right, both hidden until hero fade-in completes, then fade in over 300ms
- Lenis instantiation and GSAP ticker integration
- **Output:** open `index.html` → see the hero. Scrolling works (Lenis). Cursor warmth follows mouse. Grain overlay pulses.

**Token budget:** ~11K tokens (HTML ~2K, CSS ~3K, JS ~6K)

---

### Piece 2: Manifesto + Scroll animations

**Dependency:** Piece 1 (builds on the same `index.html`)
**What to build:**
- **Manifesto section** exactly as described: three lines of editorial copy, 40% left margin, hairline rule above, glyph at end
- GSAP ScrollTrigger animations: each line fades in with letter-spacing shift (-0.05em → 0em), first at section top entering viewport, second at 25% scroll, third at 50%. 400ms stagger between lines.
- The top bar transitions from transparent to visible on scroll past hero (opacity 0→1 with a small y offset, using a ScrollTrigger with `start: "top top"`, `end: "+=100"`)
- **Output:** scroll past hero → manifesto lines reveal one by one. Top bar fades in.

**Token budget:** ~8K tokens (HTML ~1K, CSS ~2K, JS ~5K)

---

### Piece 3: The Works grid + hover effects

**Dependency:** Pieces 1, 2 (adds to existing)
**What to build:**
- **The Works** grid section: 3×2 CSS grid, 6 cards as described. Each card: number (12px), title (28px), author (14px), 3px colored stripe (amber #D4A373 or rose #C77DFF), 3-word excerpt in italic
- Card hover: stripe widens 60px→100%, title letter-spacing tightens by 0.02em, subtle dark-gray card background (5% opacity)
- GSAP ScrollTrigger row-by-row stagger: [01+02], then [03+04], then [05+06]. Each card fades up + y: 40px→0 + number slides in from left. 200ms stagger per row.
- **Output:** scroll past manifesto → cards animate in by row. Hover any card → stripe expands, title tightens.

**Token budget:** ~12K tokens (HTML ~3K, CSS ~4K, JS ~5K)

---

### Piece 4: Capabilities + The Vault + SVG morph

**Dependency:** Pieces 1–3
**What to build:**
- **Capabilities** section: 4-column flex/grid layout, each with tiny SVG glyph (diamond-line in 4 orientations: top, bottom, left, right), headline, one-line copy. GSAP ScrollTrigger left-to-right stagger 150ms delay. Thin top rule.
- **The Vault** section: "Secure" in 120px, centered. Below it, a 48px SVG that starts as a circle with a vertical bar (minimal lock) and morphs to a checkmark inside a circle. Use inline SVG with GSAP `MorphSVG` plugin or manual path interpolation via `attr` tween. The morph scrubs with ScrollTrigger (`start: "top center+=20%"`, `end: "center center"`, `scrub: 1`). Below: "Biometric. Encrypted. Yours alone." in 14px gray.
- **Output:** scroll past The Works → capabilities fade in column-by-column. Scroll further → "Secure" fades in, lock morphs to checkmark tied to scroll position.

**Token budget:** ~13K tokens (HTML ~2K, CSS ~2K, SVG ~2K, JS ~7K)

---

### Piece 5: Cross-Platform + CTA + polish

**Dependency:** Pieces 1–4 (final polish piece)
**What to build:**
- **Cross-Platform** section: two lines + glyph. Full-width hairline rules above and below. Fade-in ScrollTrigger, 500ms.
- **CTA** section: glyph with pulse animation (CSS keyframes, 4s loop, opacity 0.4→0.7). "Illuminate what matters" centered. Underline hover effect: `::after` pseudo-element with `transform: scaleX(0)` → `transform: scaleX(1)` on hover, `transform-origin: center`, 400ms ease. Footer text in 11px dark gray 40% opacity.
- **GSAP ScrollTrigger cleanup:** Register all ScrollTriggers, call `ScrollTrigger.refresh()` on Lenis scroll. Ensure no orphaned animations.
- **Responsive pass:** Hero font scales down for mobile (200px → 100px on screens <768px, 140px on <1024px). Grid goes 1 column on <768px. Manifesto margin reduces to 10% on mobile. Test at 375px, 768px, 1024px, 1440px. Use `clamp()` for font sizes where appropriate.
- **SEO meta:** Add `<title>`, `<meta description>`, `<meta viewport>`, Open Graph tags, favicon (SVG of the glyph, inlined as data-URI).
- **Performance check:** Total page weight under 200KB (excluding fonts). No render-blocking resources beyond the CSS in `<style>`. GSAP and Lenis loaded async/defer.
- **Output:** Full page. Everything works. Scroll from hero through CTA. All animations smooth. Responsive. Clean.

**Token budget:** ~14K tokens (HTML ~3K, CSS ~4K, JS ~7K)

---

### Total build order

```
Piece 1 ──→ Piece 2 ──→ Piece 3 ──→ Piece 4 ──→ Piece 5
(hero)     (manifesto) (works)     (cap+vault) (cta+polish)
```

Each soldier checks their piece works in-browser before passing to the next. Piece 5 is the final shippable output.

---

## Section 4: Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg` | `#0A0A0A` | Page background — near-black, warmer than `#000` |
| `--text-primary` | `#F0EDE8` | Warm white — main body and hero type |
| `--text-secondary` | `#8A8682` | Gray — secondary copy, author lines, footnotes |
| `--text-tertiary` | `#5C5A57` | Muted — numbers, meta, dividers |
| `--accent-amber` | `#D4A373` | Highlight stripe (cards 01, 03, 05) — warm amber, like dried highlighter ink |
| `--accent-rose` | `#C77DFF` | Highlight stripe (cards 02, 04, 06) — soft violet-rose, complementary to amber |
| `--border` | `#1F1E1C` | Hairline rules, card dividers — one step off background |
| `--hover-bg` | `rgba(240, 237, 232, 0.04)` | Card hover overlay — barely perceptible brightening |

### Why this palette works

Near-black (`#0A0A0A`) instead of pure `#000` — pure black is dead; `#0A0A0A` suggests depth, like a studio with the lights dimmed but not off. Warm white (`#F0EDE8`) instead of `#FFFFFF` — cold white is corporate; warm white is editorial, like a page in a well-worn book. Two accent colors (amber and rose) instead of one — the pair creates a system without needing icons or UI chrome; the stripe color alone distinguishes cards.

### Font pairings

- **Display (hero, manifesto, section headers):** Playfair Display — its sharp serifs carry editorial weight
- **Body (cards, capabilities, copy):** Inter — clean, surgical, modern. The serif/sans-serif contrast is the only "animation" the typography needs.

---

## Design Principles (for implementers)

1. **If it doesn't need to move, it doesn't move.** Every animation has a specific job: reveal information, guide attention, or emphasize a transition. No decorative motion.
2. **Typography is the interface.** The user navigates by reading, not by clicking. Every section is a paragraph, not a widget.
3. **Space is the luxury.** Padding is generous. Margins are wide. The page should feel like a limited-edition art book, not a dashboard.
4. **The glyph is the brand.** It appears in exactly 4 places: under the hero, at the end of the manifesto, centered between sections, and above the CTA. No logo lockup. No wordmark. Just the glyph.
5. **Wait before showing.** The hero's 1s blackout on page load (the fade-in) is intentional — it says "settle in. This will be worth your attention."
6. **GSAP is not a toy.** Only three ScrollTrigger uses: (a) staggered letter-spacing reveals on manifesto, (b) card stagger on Works, (c) SVG morph on Vault. That's it. Anything else is CSS transitions.
7. **Mobile is not an afterthought.** The page works at 375px. The design tightens but doesn't break. The experience is the same: dark luxury, massive type, generous space — just scaled down.
