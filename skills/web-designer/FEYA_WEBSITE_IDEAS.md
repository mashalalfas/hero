# Feya PDF — Website Ideas

## Council: 2026-06-18
### Verdict: UNANIMOUS (3/3 analysts converge on core strategy)

---

## Section 1: The Big Idea (Convergence — all agree)

Feya's website should **not** look like a PDF reader website. The PDF reader market is commoditized — Adobe, Foxit, PDF Expert all show the same thing: screenshots of documents with toolbars. Feya is different because it treats PDF reading as a **sensual, premium experience** — the quiet joy of highlighting a passage, the security of a biometric vault, the satisfaction of smooth continuous scroll.

The core metaphor all analysts converged on: **Feya is not a tool — it's a reading sanctuary.** The website should feel like opening a beautifully-bound journal in a dimly-lit library. Dark mode as default. Warm accent colors (amber, gold, deep violet) instead of cold blue/white enterprise palettes. Every animation should evoke the tactile pleasure of interacting with paper — the soft glow of a highlighter pen, the satisfying click of a vault unlocking, the whisper of pages flowing.

The brand signature: **"Illuminate what matters."** Highlighting is the hero feature. The website leads with that gesture — not as a UI demo, but as a philosophy.

---

## Section 2: Three Website Concepts

---

### Concept A: "The Highlight"
- **Vibe:** Dark, luminous, editorial
- **One-liner:** The entire website is a demonstration of illumination — text appears in shadow until you "highlight" it with cursor movement, revealing meaning.
- **Key sections:**
  1. Hero — dark void with floating text fragments; cursor leaves glowing highlighter trails in amber/rose/violet
  2. "The Gesture" — show highlights being made, persisting, being organized (uses Three.js particle trails)
  3. "The Vault" — biometric unlock animation using GSAP morphing (PIN pad → fingerprint icon → unlock)
  4. "The Library" — grid of document covers that sort/filter with smooth GSAP stagger animations
  5. "Cross-Platform" — phone and tablet mockups with synchronized scroll, GSAP ScrollTrigger driving both
  6. CTA — "Start highlighting" with a highlighter-pen drawing the button border on hover
- **Animation hook:** Three.js particle trail system + GSAP ScrollTrigger. When user scrolls over text blocks, a neon highlighter stroke draws across the text, leaving it permanently "revealed" in full color. Built with Three.js `Points` geometry for the glow trail and GSAP `ScrollTrigger` scrub for the draw effect.
- **Soldier task split (5 pieces, build order → sequential then parallel):**

  **Piece 1 (Sequential — HTML/CSS skeleton + Hero):**
  - Full page HTML structure, Tailwind setup, dark theme CSS variables
  - Hero section: dark gradient background, floating text fragments, cursor-following highlighter effect (CSS + JS)
  - GSAP loaded, Lenis smooth scroll initialized
  - ~15K tokens

  **Piece 2 (Sequential — Three.js highlight effect):**
  - Three.js scene overlaid on hero (alpha: true, z-index layers)
  - Particle system: points that follow mouse path, color transitions amber→rose→violet
  - Disposed on scroll past hero (IntersectionObserver + cleanup)
  - ~12K tokens

  **Piece 3 (Parallel with 4 — Feature sections 2+3):**
  - "The Gesture" section: staggered text reveal with GSAP ScrollTrigger
  - "The Vault" section: SVG morph animation (PIN pad → fingerprint → checkmark), GSAP MorphSVG or manual path morphing
  - Lottie/canvas animation of persistent highlights on mock PDF pages
  - ~18K tokens

  **Piece 4 (Parallel with 3 — Feature sections 4+5+CTA):**
  - "The Library" section: CSS grid of document cards with GSAP stagger reveal
  - "Cross-Platform" section: two device mockups with synchronized scroll (gsap.matchMedia for responsive)
  - CTA section: interactive button with highlighter hover effect
  - ~15K tokens

  **Piece 5 (Sequential — Polish, responsive, a11y):**
  - `prefers-reduced-motion` fallbacks via `gsap.matchMedia()`
  - Mobile responsive: stack sections vertically, reduce particle complexity
  - Performance: `will-change` on animated elements, content-visibility on below-fold sections
  - ~10K tokens

---

### Concept B: "Paper & Pixel"
- **Vibe:** Warm, tactile, natural
- **One-liner:** The bridge between paper's soul and pixel's power — a website that feels like touching handmade paper.
- **Key sections:**
  1. Hero — large format paper texture (Three.js plane with subtle displacement map, simulates paper fiber moving like breath)
  2. "The Reading Experience" — continuous scroll visualization: text on paper-like background that flows upward as you scroll, using a vertical scroll-linked animation with GSAP scrub
  3. "The Annotations" — sketchy, hand-drawn style UI elements animate into existence (underline wiggles, sticky notes unfold, highlight strokes appear hand-drawn with anime.js)
  4. "Your Documents, Your Vault" — flips to premium/secure tone: dark paper texture, golden accents, biometric pad animation
  5. "On Every Device" — three device frames (phone, tablet, desktop) showing the same document with the same highlights synchronized
  6. Footer — simple, elegant, warm-toned
- **Animation hook:** Three.js displacement-mapped paper texture that responds to scroll as if the paper is breathing. GSAP timeline with scrub drives the displacement amplitude. Overlaid with Lenis smooth scroll for buttery page turns.
- **Soldier task split (4 pieces, build order → sequential then two parallel):**

  **Piece 1 (Sequential — HTML/CSS + Hero setup):**
  - HTML structure, Tailwind + warm color palette (cream #F5F0E8, parchment #EDE4D4, ink #2C2416, gold #C8A84E)
  - Hero layout: Three.js canvas overlay + text overlay
  - Lenis smooth scroll
  - Paper displacement map generation (procedural canvas noise or loaded image)
  - ~14K tokens

  **Piece 2 (Sequential — Three.js paper breathing + scroll sync):**
  - Three.js scene: PlaneGeometry with displacement map, MeshStandardMaterial
  - GSAP ScrollTrigger scrub drives `displacementScale` from 0.0 → 0.05 → 0.0 on scroll
  - Subtle ambient light warm lighting
  - Cleanup on unmount
  - ~14K tokens

  **Piece 3 (Parallel with 4 — "Reading" + "Annotations" sections):**
  - Continuous scroll section: text blocks reveal with GSAP ScrollTrigger, clip-path reveal animation simulating text "emerging" from paper
  - Annotations section: anime.js timeline — highlighter strokes draw themselves, sticky notes tumble in with spring physics, underlines wiggle into place
  - ~18K tokens

  **Piece 4 (Parallel with 3 — "Vault" + "Devices" + CTA):**
  - Vault section: transitions from warm to dark paper (`background: linear-gradient` animated with ScrollTrigger), biometric animation (Lottie or canvas)
  - Devices section: three device frames with synchronized mockups, GSAP `matchMedia` for responsive
  - CTA: button that looks like a wax seal stamp — SVG hover animation
  - ~16K tokens

---

### Concept C: "The Vault"
- **Vibe:** Dark luxury, secure, architectural
- **One-liner:** Your documents deserve a vault, not a folder — minimalist monumentalism meets biometric elegance.
- **Key sections:**
  1. Hero — massive typography "Illuminate what matters" with a subtle Three.js point cloud orbiting behind it; a glowing geometric lock icon pulses at center
  2. "Unlock" — interactive demo: a PIN pad animates in with GSAP stagger per key; type (simulated) and a fingerprint icon appears, morphs to a checkmark; the "document" behind fades in
  3. "Read" — continuous scroll view of a document; the text is rendered as floating particles that resolve into readable text as you "focus" (scroll into center → GSAP scrub drives blur → clear)
  4. "Organize" — architectural grid of documents, each one a "vault" with its own security level indicator; GSAP stagger + flip animation on sort
  5. "Always with you" — cross-platform with elegant minimal mockups, no bezels, floating in dark space
  6. CTA — dark glassmorphism card with "Start securing your reading" CTA
- **Animation hook:** Three.js particle cloud (2000+ points) that morphs from a geometric lock shape into free orbit and back. GSAP drives the point positions between two states (locked cube vs orbiting sphere) via ScrollTrigger scrub.
- **Soldier task split (5 pieces, build order → sequential → parallel → merge):**

  **Piece 1 (Sequential — HTML/CSS skeleton + dark luxury theme):**
  - HTML structure, Tailwind setup, dark theme (bg #0A0A0F, surface #14141E, accent #C8A84E gold, text #F0EDE8)
  - Hero layout with massive typography (clamp font-size)
  - GSAP + Lenis initialization
  - Canvas container for Three.js overlay
  - ~12K tokens

  **Piece 2 (Sequential — Three.js particle cloud):**
  - Three.js Points geometry: 2000 particles
  - Two target shapes: cube (locked state) and sphere (free state)
  - GSAP timeline animates particle positions between the two on scroll (using ScrollTrigger scrub)
  - Color transitions: amber → deep violet → amber loop
  - ~16K tokens

  **Piece 3 (Parallel with 4 — "Unlock" + "Read" sections):**
  - "Unlock" section: interactive PIN pad mockup — SVG grid of number keys, GSAP stagger entry (0.04s delay each), CSS hover glow on keys
  - "Read" section: text particle blur → clear effect — each word is a `<span>`, GSAP ScrollTrigger sets `filter: blur(8px)` to `blur(0px)` per word as it enters viewport center
  - ~18K tokens

  **Piece 4 (Parallel with 3 — "Organize" + "Devices" + CTA):**
  - "Organize" section: CSS grid of document cards with security badges, GSAP Flip animation on category filter buttons
  - "Always with you": three device mockups floating in dark space, subtle y-axis float animation (GSAP infinite loop, paused outside viewport)
  - CTA: glassmorphism card with `backdrop-filter: blur(20px)`, hover glow effect on button
  - ~14K tokens

  **Piece 5 (Sequential — Merge + Polish):**
  - Merge all sections, test scroll flow
  - `prefers-reduced-motion` fallbacks: replace particle animation with static gradient, replace stagger with simple fade
  - Performance: `content-visibility: auto` on below-fold, `will-change: transform` on Three.js canvas
  - Mobile: reduce particles to 500, stack grid to single column
  - ~10K tokens

---

## Section 3: Split / Minority Views

**Minority view (Analyst 2 — Paper & Pixel advocate):**
Argues that a warm, natural feel ("Paper & Pixel") differentiates Feya better from the cold enterprise vibe of Adobe and Foxit. "The Highlight" is too dark/cyberpunk for a reading app. PDFs are about *content*, not flash — the paper texture feels intellectually honest.

**Minority view (Analyst 3 — The Vault advocate):**
Counters that security is the most under-tapped differentiator in the PDF reader space. No one markets PDF readers as "secure." The biometric unlock + passphrase meter are Feya's moat. "The Vault" positions Feya as a premium secure product, which justifies a higher price point.

**Consensus resolution:**
Design the website so "The Highlight" is the **primary visual language** (the header, the hero, the brand hook) but incorporate the vault/security section as a **distinct visual drop** — transitioning from luminous dark to architectural dark. The warm paper aesthetic is relegated to a "Reading Experience" sub-section rather than the full site theme. This gives Feya a unique identity that doesn't look like any other PDF reader, while still covering all features.

---

## Section 4: Recommended MVP (build this first)

### ✅ Concept A: "The Highlight" — with vault sub-section from Concept C

**Why:**
1. **Most visually unique** — no PDF reader website uses dark mode + highlighter-as-gesture. Instantly recognizable.
2. **Easiest for a 64K context soldier** — Three.js particle trails are simpler than displacement-mapped paper or morphing particle clouds. The highlight trail is a proven pattern (many codepens, well-documented).
3. **Aligns with Feya's strongest feature** — persistent highlighting with color picker is the app's most demo-worthy feature. The website should sell the *feeling* of highlighting, not just show a screenshot.
4. **GSAP ScrollTrigger is the hero** — the skill card specifically mentions `ScrollTrigger.scrub()` as a P0 pattern. The highlight trail effect is a textbook ScrollTrigger demo.

**Build order (5 pieces, soldier-friendly):**

```
PIECE 1 [SEQUENTIAL] → HTML/CSS skeleton + Hero layout + GSAP/Lenis init
PIECE 2 [SEQUENTIAL] → Three.js particle trail effect (hero only)
PIECE 3 [PARALLEL]   → "The Gesture" + "The Vault" feature sections
PIECE 4 [PARALLEL]   → "The Library" + "Cross-Platform" + CTA sections
PIECE 5 [SEQUENTIAL] → Polish: a11y, responsive, performance
```

**Estimated total Soldier load:** ~68K tokens across 5 pieces (all ≤ 18K tokens per piece ✅)
**Estimated build time:** 3-4 passes (each piece is one soldier call)

**Stitch step (after all 5 pieces complete):**
- A final soldier pass to merge all pieces into a single `index.html`
- Ensure Lenis runs once at root
- Fix any ScrollTrigger offset conflicts between sections
- Validate responsive breakpoints

---

## Section 5: Inspiration References

### Live product websites referenced:

| Website | URL | What to borrow |
|---------|-----|-----------------|
| Linear | https://linear.app | Dark minimal hero, bug-tracker-as-art aesthetic, scroll-linked animated UI mockups |
| Stripe | https://stripe.com | Massive gradient-driven hero, micro-interactions on every hover, clean information hierarchy |
| Superhuman | https://superhuman.com | Dark mode by default, interface screenshots embedded in scroll narrative, "speed" as visual language |
| GoodNotes | https://www.goodnotes.com | Warm paper-to-digital bridge, social proof as narrative, "wherever you work" lifestyle shots |
| PDF Expert | https://pdfexpert.com | Clean feature sectioning, before/after comparisons, tool-focused copy |
| Notion | https://notion.so | Block-based scroll narrative, minimalist mockups, playful cursor effects |

### Design system / animation references:

| Reference | What to steal |
|-----------|---------------|
| Codepen — Particle text trail | Highlighter glow effect pattern (Three.js Points + mouse tracking) |
| Apple's "Shot on iPhone" campaign | Dark background with glowing accent colors, product as art |
| A24 film posters | Typography as hero element, editorial dark luxury, minimal color palette |
| Arc Browser website | Browser-as-product-sell, scroll-driven narrative with embedded interactive demos |

---

## Appendix: Brand Color Palette (recommended for all concepts)

```
--bg-primary:    #0B0B10   (near-black with subtle blue)
--bg-secondary:  #14141E   (dark surface)
--surface:       #1C1C2A   (card backgrounds)
--accent-amber:  #D4A84B   (primary highlight — warm gold)
--accent-rose:   #C85A7A   (secondary highlight — rose)
--accent-violet: #7C5CBF   (tertiary highlight — violet)
--text-primary:  #F0EDE8   (warm white)
--text-muted:    #8B8794   (gray)
--success-green: #4CAF50   (biometric unlock)
--glass-bg:      rgba(20, 20, 30, 0.7)
--glass-border:  rgba(255, 255, 255, 0.08)
```

**Typography recommendation:**
- Headings: **Instrument Serif** or **Tiempos Text** — editorial, warm, refined
- Body: **SF Pro Display** or **Inter** — clean, readable, modern
- Accent/display: **Space Grotesk** for tech-forward energy in the vault sections

---

*End of Council Report. All three analysts approve this document for handoff to the web-designer soldier.*
