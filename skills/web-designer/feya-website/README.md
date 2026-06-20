# Feya PDF — Website

> **Canonical source** of the Feya PDF landing page.

## Location

```
hero/skills/web-designer/feya-website/index.html
```

## Deployment

GitHub Pages serves from the `gh-pages` branch of `mashalalfas/FeyaPDF`:

- **Live:** https://mashalalfas.github.io/FeyaPDF/

The `index.html` from this directory is the single source. When deploying, copy it into the FeyaPDF repo's `gh-pages` branch and push.

## Design

Minimal dark theme. Single vertical scroll. Six sections:

| Section | Content |
|---------|---------|
| Hero | "Feya" in Playfair Display + Glyph (diamond on line) |
| Manifesto | Three editorial lines about reading |
| Works | Grid of 6 literary works with stripes |
| Capabilities | Read · Highlight · Secure · Sync |
| Vault | "Secure" with biometric/lock icon |
| CTA | "Illuminate what matters" |

Built with vanilla HTML/CSS/JS — no frameworks, no build step.
GSAP + ScrollTrigger + Lenis loaded from CDN for scroll animations.

## Tech

- **CSS**: Custom properties, grain texture overlay, cursor warmth
- **JS**: GSAP 3.12, ScrollTrigger, Lenis 1.1.18
- **Fonts**: Playfair Display (headings), Inter (body)
- **Deploy**: Push to `mashalalfas/FeyaPDF@gh-pages`

## History

The first deployed design ("The Apprentice's Desk") — a warm paper-tone 7-section page with Three.js desk scene, flipbook, ink palette, wax seal, ember animations — was built in the standalone FeyaPDF repo. It was the wrong design. The correct minimal dark design lives here in the HERO repo. Old source files are archived in `FeyaPDF/website__old_design/`.
