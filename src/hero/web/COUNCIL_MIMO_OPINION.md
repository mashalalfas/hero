# Council Opinion — MiMo Pro (Implementation)
**HERO Viewport Dashboard v4**
**Date:** 2026-05-30

---

## 1. SPA or Multi-page? Keep FastAPI+vanilla JS or Pivot?

**Keep FastAPI + vanilla JS. Do NOT pivot to React/Vue/Svelte.**

Here's why this is non-negotiable:

- The current server works. It serves HTML, streams SSE, returns JSON. That's a solid backbone.
- Vanilla JS with modern DOM APIs (querySelector, fetch, EventSource, custom elements) is more than enough for a 3-tab dashboard.
- A framework adds a build step, node_modules, bundler config, and a whole ecosystem of opinions you'll fight for a 3-tab app.
- The existing codebase already has working SSE streaming and sandbox data. That's 60% of the hard problem solved.

**However — and this is important — "vanilla JS" does not mean "no structure."** I'd use a tiny pattern:

- Each tab is a Web Component (custom element) that mounts/unmounts cleanly.
- A central `DashboardState` object holds all sandbox data, updated via SSE.
- Tabs subscribe to state changes. No re-rendering the whole page when one sandbox updates.
- Use `lit` or nothing. Lit is 5KB, gives you reactive templates, and doesn't require a build step. But if you want pure vanilla, that works too.

**Verdict:** FastAPI backend. Vanilla JS or Lit frontend. Single HTML page with tab switching. No build step. `python server.py` and go.

---

## 2. What Survives? What Dies?

Let me be honest about what I'd keep:

### KEEP (reuse as-is or with minor edits):
- `server.py` — FastAPI app, SSE endpoints, sandbox data fetching. This is the backbone.
- `sandbox_reader.py` — Reads TOON state from sandbox files. Core data layer.
- The SSE streaming logic — real-time updates are working and that's valuable.
- `hero-status.json` (or wherever sandbox state lives) — the data format is fine.

### KEEP BUT REWRITE:
- `static/index.html` — The entry point stays, but the content becomes a shell for tab components.
- `static/app.js` — Replace the current monolithic JS with the Web Component architecture.

### DELETE:
- The current tab implementation (if it's a single-page dump of all sandbox data).
- Any inline styles in HTML — move to a proper CSS file.
- The current `static/dashboard.js` (if it exists) — it's doing too much in one file.

### BUILD NEW:
- `static/components/overall-tab.js` — Grid of all 12 sandboxes, status cards.
- `static/components/active-tab.js` — Rich per-project page (this is the crown jewel).
- `static/components/archived-tab.js` — Dead/idle projects, muted display.
- `static/components/sandbox-card.js` — Reusable card component.
- `static/components/nav-bar.js` — Tab navigation.
- `static/styles.css` — All styling in one place.
- `static/components/active-detail.js` — Deep-dive view for active projects.

**Bottom line:** The server stays. The frontend gets a surgical rewrite. The data layer is untouched.

---

## 3. Separate App or Extend Current Server?

**Extend. Do NOT create a separate app.**

Arguments for separate app:
- Mashal suggested it
- Clean separation of concerns
- Can be developed independently

Arguments against separate app:
- Two servers to manage, two ports, two processes
- Data duplication — both need sandbox state
- Deployment complexity doubles
- The current server already does 90% of what's needed

**The real answer:** The current server is the dashboard. We're reskinning it, not replacing it. Create a new branch, rewrite the frontend, ship.

If you really want isolation, use a feature flag in the FastAPI app: `/v4/dashboard` serves the new UI, `/` still serves the old one. Same process, different routes. That's clean separation without the operational overhead.

**Verdict:** Same server. Same port. New frontend. Feature flag if needed.

---

## 4. Build Order — What Gets Built First?

This is where most dashboard redesigns go wrong. You build the cool stuff first and then realize the foundation is broken.

**Build order (my recommendation):**

### Phase 1: Data Layer (Day 1)
- Verify the SSE endpoint works correctly with 12 sandboxes.
- Test: Can I subscribe and get all sandbox states? Is the data shape clean?
- Output: Confirmed API contract. If the data shape is messy, fix it NOW.

### Phase 2: Navigation Shell (Day 1-2)
- Single HTML page with 3 tabs: Overall, Active, Archived.
- Tab switching with no content yet — just the UI skeleton.
- CSS variables for theming.
- Output: Clicking tabs switches views. Empty views. Clean.

### Phase 3: Overall Tab (Day 2-3)
- Grid of 12 sandbox cards.
- Each card shows: name, status (active/idle/dead), last activity, token usage.
- Color-coded: green=active, yellow=idle, red=dead.
- Output: You can see all sandboxes at a glance. This is your "war room" view.

### Phase 4: Active Tab — First Pass (Day 3-4)
- This is the hard part. Start with a single active project (quranaudio).
- Full-page view: project name, description, files, recent sessions, token burn, TOON state.
- Make it feel rich but not overwhelming.
- Output: One project page works. Feels good.

### Phase 5: Active Tab — All Projects (Day 4-5)
- Extend to show all active projects as sub-tabs or a sidebar list.
- Each project gets its own rich page.
- Navigation between projects.

### Phase 6: Archived Tab (Day 5)
- List of dead/idle projects.
- Muted styling, less detail.
- Easy to restore if needed.

### Phase 7: Polish (Day 6)
- Loading states, error handling, edge cases.
- Keyboard navigation.
- Mobile-friendly (if needed).

**Total: 6-7 days for a solo builder.**

---

## 5. The Riskiest Part: "Needs Literature to Navigate"

This is the phrase that worries me. "Needs literature to navigate" could mean:

1. The project has complex documentation that needs to be displayed inline.
2. The user needs to read docs before understanding the dashboard.
3. The projects themselves have extensive READMEs, specs, and design docs.

**My approach:**

**Don't build a documentation viewer. Build a context panel.**

Here's what I mean:

- When you click on a project in the Active tab, you see:
  - **Status overview** (3 seconds to understand)
  - **Recent activity** (what happened last)
  - **Key files** (not all files — just the important ones: README, AGENTS.md, SPEC.md)
  - **Inline summaries** of key docs (not the full text — auto-generated 2-paragraph summaries)
  - **Links** to full docs if you need to go deeper

- The "literature" is NOT a wall of text. It's structured, scannable, with clear hierarchy:
  - What is this project?
  - What's it doing right now?
  - What needs attention?
  - Where do I go for details?

**The trap to avoid:** Building a markdown renderer that dumps 50-page specs into the UI. That's not navigation — that's a PDF viewer.

**What I'd actually build:**
- Parse `AGENTS.md`, `README.md`, `SPEC.md` from each sandbox.
- Extract key sections (overview, current status, known issues).
- Display them as collapsible panels.
- Link to full files in the sandbox directory.

**Risk mitigation:** Start with quranaudio only. Build the context panel for one project. If it feels good, extend to others. If it feels cluttered, simplify.

---

## 6. Concrete Build Timeline

### Day 1: Foundation
- Morning: Audit existing server, confirm SSE works, document API contract.
- Afternoon: Build navigation shell (HTML + CSS + tab switching).
- **Ship:** Empty tabs that switch. No data yet.

### Day 2: Data Integration
- Morning: Connect SSE to Overall tab. Display 12 sandbox cards.
- Afternoon: Style the cards. Add status colors, hover states, tooltips.
- **Ship:** Overall tab shows all sandboxes. Looks decent.

### Day 3: Active Tab — Core
- Morning: Build project detail view for quranaudio.
- Afternoon: Pull in sandbox files, display README summary, recent sessions.
- **Ship:** Active tab shows one project in detail. Feels rich.

### Day 4: Active Tab — Multi-project
- Morning: Add project selector/list in Active tab.
- Afternoon: Extend detail view to work with any active project.
- **Ship:** Active tab handles multiple projects.

### Day 5: Archived + Polish
- Morning: Build Archived tab. List dead/idle projects.
- Afternoon: Loading states, error handling, keyboard nav.
- **Ship:** All three tabs functional. Error states handled.

### Day 6: The "Literature" Feature
- Morning: Build context panel for active projects. Parse key docs.
- Afternoon: Collapsible panels, inline summaries, links to full docs.
- **Ship:** Projects have rich context panels. Feels sophisticated.

### Day 7: Final Polish
- Morning: Performance check. SSE reconnection. Edge cases.
- Afternoon: Code review, documentation, deploy to 192.168.8.149:8765.
- **Ship:** Dashboard v4 live.

---

## 7. Solo Builder: Where to Cut Corners vs. Where to Go Deep

### CUT CORNERS (save time, nobody will notice):
- **No build step.** Zero. No webpack, no vite, no node. Just serve static files.
- **No tests for the frontend.** It's a dashboard, not a banking app. Manual testing is fine.
- **No state management library.** A plain JS object with listeners is enough for 12 sandboxes.
- **No CSS framework.** Write 200 lines of CSS. It's faster than learning Tailwind's class soup.
- **No animations.** Fade transitions are nice but not essential. Ship functional first.
- **No mobile support.** This is a desktop dashboard for a power user. Don't waste time on responsive design.
- **No auth.** It's on a private network. Don't over-engineer security.

### GO DEEP (this is where quality lives):
- **The SSE data layer.** If this is flaky, the whole dashboard is useless. Test reconnection, handle dropped connections, add retry logic.
- **The Overall tab grid.** This is the first thing you see. Make it feel professional. Clean spacing, consistent card sizes, clear status indicators.
- **The Active project detail page.** This is where users spend 80% of their time. Make it rich, scannable, and informative.
- **Error states.** What happens when a sandbox is unreachable? When SSE drops? When data is stale? Handle these gracefully.
- **The "literature" context panel.** This is the differentiator. If done well, it makes the dashboard feel smart.

---

## 8. Making It Feel Sophisticated Without Bloat

**The secret: restraint + consistency.**

Here's what I'd actually reach for:

### Libraries (if any):
- **Lit** (5KB) — Optional. For Web Components with reactive templates. But vanilla JS works too.
- **No framework.** React, Vue, Svelte — all overkill for 3 tabs.
- **No CSS framework.** Custom CSS with CSS variables for theming.

### Patterns:
- **CSS Variables for theming.** One `:root` block defines all colors, spacing, fonts. Change the theme in one place.
- **Web Components for tab isolation.** Each tab is a custom element. Clean boundaries, easy to test.
- **Event-driven updates.** SSE pushes data → state updates → components re-render. Simple pipeline.
- **Progressive disclosure.** Show summary first, details on click. Don't overwhelm.

### Design Principles:
- **Whitespace is your friend.** Don't cram everything together. Let the UI breathe.
- **Consistent typography.** One font family, 3-4 sizes max.
- **Color with purpose.** Green = active, yellow = idle, red = dead. No other colors needed.
- **Subtle shadows and borders.** Not flat, not skeuomorphic. Just enough depth to separate elements.
- **Keyboard navigation.** Arrow keys to switch tabs, Enter to select projects. Feels professional.

### What "Sophisticated" Actually Means:
- Not busy. Clean.
- Not loud. Confident.
- Not cluttered. Focused.
- Not slow. Responsive.

**The dashboard should feel like a well-designed CLI tool — functional, clear, no wasted pixels.**

---

## Final Verdict

This is a 7-day build for a solo developer. The current server stays. The frontend gets rewritten with Web Components. The data layer is untouched. The "literature" feature is a context panel, not a documentation viewer.

**Key risk:** Over-engineering the "literature" feature. Start with one project, build a simple context panel, extend only if it works.

**Key opportunity:** Making the Active project detail page so good that it becomes the primary interface for understanding projects. That's where the value lives.

**My commitment:** I will build this. FastAPI backend stays. Vanilla JS frontend. Clean CSS. Web Components. 7 days. Ship it.

---

*— MiMo Pro, Implementation Council*
*"Ship it, then polish it. Never polish it, then ship it."*
