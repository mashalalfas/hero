# COUNCIL OPINION — GLM 5.1 (UX & Edge Cases)

**Subject:** Viewport Dashboard v4 — User Experience, Mobile, and Edge Cases  
**Date:** 2026-05-30  
**Stance:** The current UI is a desktop-only toy. A "sophisticated" active page means solving the hard UX problems that nobody wants to think about: empty states, SSE disconnects, transitions, and mobile.

---

## The Problem I See

The current dashboard looks fine on a 1920px monitor. On a phone, it's a disaster — the card grid doesn't reflow well, the detail drawer covers the entire screen with no back gesture, and there's no tab navigation at all. The "rich active page" Mashal wants requires solving 15+ states that the current codebase completely ignores.

Let me be blunt: **the current code has zero empty states, zero loading skeletons, zero error boundaries, and zero accessibility attributes beyond `aria-modal` on the drawer.** That's not a dashboard. That's a demo.

## What's Wrong With the Current UX

### 1. The Flat Grid Is the Wrong Metaphor
Twelve cards in a grid is fine for monitoring. It's terrible for "navigate this project's full context." You can't show pipeline state, agent hierarchy, token history, timeline, and issues in a card. The detail drawer is the right idea but the wrong implementation — it's a side panel that fights for horizontal space on desktop and obliterates context on mobile.

### 2. No State Machine
There's no concept of the dashboard's own states. What does the user see while SSE is connecting? While the first fetch is loading? When the API returns a 500? When the token expires mid-session? Right now: nothing. The dashboard renders an empty grid and hopes for the best.

### 3. No Accessibility
- Tab navigation: broken. Cards are clickable divs with no `role="button"`, no `tabindex`, no keyboard handlers.
- Screen readers: the sandbox name is just text in a div. No `aria-label`, no landmark roles.
- Color contrast: the status badges use colored text on colored backgrounds. WCAG AA failure.
- Motion: animations.css has no `prefers-reduced-motion` media query.

### 4. Mobile Is an Afterthought
The `viewport` meta tag says `user-scalable=no`. The CSS uses `var(--space-3)` for padding but there's no breakpoint system. The card grid is `display: grid` with no responsive columns. On a 375px screen, you get one card per row with 16px padding. That's not a dashboard. That's a list.

## My Stance: How the 3-Tab Navigation Should Work

### Mobile-First Tab Architecture

```
┌──────────────────────────────┐
│ ☰  HERO Viewport        🔵  │  ← Status dot (green=connected, red=disconnected)
├──────────────────────────────┤
│ [Overall] [Active] [Archive] │  ← Tab bar, sticky below header
├──────────────────────────────┤
│                              │
│  (Active tab content)        │  ← Full-page project view
│                              │
│                              │
│                              │
│                              │
├──────────────────────────────┤
│        (scrollable)          │
└──────────────────────────────┘
```

**Tab bar behavior:**
- Sticky at top, below header
- Horizontal scroll on overflow (not wrapping)
- Active tab has underline indicator with slide animation
- Swipe between tabs on mobile (with momentum)
- Tab badges: "Overall (12)", "Active (3)", "Archived (9)"

### The Active Tab: Rich Project Page

This is where it gets hard. The "rich active page" Mashal wants is essentially a **project detail page** with 8+ sections. Here's my layout:

```
┌──────────────────────────────┐
│ ← Back to Active    freya    │  ← Breadcrumb + project name
├──────────────────────────────┤
│ ● Active | Phase: Building   │  ← Status + phase badge
│ Last activity: 2 min ago     │
├──────────────────────────────┤
│                              │
│  ┌─ TOKEN USAGE ───────────┐ │
│  │ ████████░░ 72%          │ │  ← Main progress bar
│  │ 142K / 200K tokens      │ │
│  │ Burn: ~2.1K/min         │ │
│  └─────────────────────────┘ │
│                              │
│  ┌─ PIPELINE ──────────────┐ │
│  │ ✓ Planning              │ │
│  │ ✓ Building              │ │
│  │ ● Testing  (current)    │ │  ← Horizontal stepper
│  │ ○ Shipping              │ │
│  └─────────────────────────┘ │
│                              │
│  ┌─ AGENTS ────────────────┐ │
│  │ COMM: ● active  gpt-4o  │ │
│  │ LEAD: ● active  claude  │ │
│  │ ARCH: ● active  gpt-4o  │ │
│  │ SOLDIERS: 3 active       │ │  ← Collapsible section
│  │   ├─ soldier-1: working  │ │
│  │   ├─ soldier-2: idle     │ │
│  │   └─ soldier-3: working  │ │
│  │ VERIFY: ○ idle           │ │
│  └─────────────────────────┘ │
│                              │
│  ┌─ ISSUES (2) ────────────┐ │  ← Collapsible, badge count
│  │ ⚠ SSE disconnect race   │ │
│  │ 🐛 Token count drift    │ │
│  └─────────────────────────┘ │
│                              │
│  ┌─ GIT ───────────────────┐ │
│  │ branch: feature/v4      │ │
│  │ commit: a3f8c2d         │ │
│  │ ● dirty                  │ │
│  └─────────────────────────┘ │
│                              │
│  ┌─ TIMELINE ──────────────┐ │
│  │ 14:22 ● Building start  │ │  ← Vertical timeline
│  │ 14:15 ✓ Planning done   │ │
│  │ 14:00 ● Project spawned │ │
│  └─────────────────────────┘ │
│                              │
└──────────────────────────────┘
```

**Key UX decisions:**
- **Collapsible sections.** Each section starts expanded on desktop, collapsed on mobile. User can toggle.
- **Sticky token bar.** Token usage is always visible at the top. It's the most important metric.
- **No horizontal scroll in sections.** Everything stacks vertically. If a section is too wide, it wraps.

## Edge Cases Nobody Wants to Handle

### 1. SSE Disconnect Mid-View

**Current behavior:** Dashboard silently stops updating. User thinks data is live but it's stale.

**My view:** This is unacceptable. Here's what should happen:

```
1. SSE disconnect detected (EventSource.onerror)
2. Show persistent banner: "Connection lost. Reconnecting... (3s)"
3. Banner is dismissible but reappears on next disconnect
4. On reconnect: fetch full state, diff with current, show "Updated" toast
5. If reconnect fails 3x: show "Connection failed. Refresh?" with manual retry
```

The banner MUST NOT cover content. It should be a fixed bar at the bottom with `z-index` above everything.

### 2. Project Transitions Active→Archived Mid-View

**Scenario:** User is on the Active tab, reading about project "freya." Server marks it archived (10 days idle). SSE pushes the update.

**What happens:**
- Active tab: "freya" disappears from the list. User sees the project they were reading just vanished. Confusing.
- Archive tab: "freya" appears there. But the user was looking at the Active tab.

**My solution:**
- Don't remove the project from Active immediately. Add a "transitioning" badge.
- Show a toast: "freya moved to Archived (idle 10+ days)"
- If user navigates away from Active and back, the project is gone.
- The detail page stays accessible via URL even after archival.

This is a **stale-while-revalidate** pattern. The UX principle: **never remove something the user is actively looking at without warning.**

### 3. Empty States (Critical, Currently Missing)

Each tab needs a designed empty state:

**Overall (no projects at all):**
```
┌──────────────────────────────┐
│                              │
│           ⚡                 │
│    No projects yet           │
│                              │
│  Waiting for HERO to deploy  │
│  an army...                  │
│                              │
│  [Deploy a sandbox]          │  ← Action button
│                              │
└──────────────────────────────┘
```

**Active (all projects archived):**
```
┌──────────────────────────────┐
│                              │
│           📦                │
│    All projects archived     │
│                              │
│  No active projects right    │
│  now. Check the Archive tab  │
│  for recent projects.        │
│                              │
└──────────────────────────────┘
```

**Archived (nothing archived yet):**
```
┌──────────────────────────────┐
│                              │
│           🕐                │
│    Nothing archived yet      │
│                              │
│  Projects will appear here   │
│  after 10+ days of inactivity│
│                              │
└──────────────────────────────┘
```

**Active project detail (no data):**
```
┌──────────────────────────────┐
│ ← Back to Active    freya    │
├──────────────────────────────┤
│                              │
│           📊                │
│    Waiting for data...       │
│                              │
│  This project was recently   │
│  spawned. Data will appear   │
│  as agents start working.    │
│                              │
│  ● SSE connected — live      │
│                              │
└──────────────────────────────┘
```

### 4. Loading States

Don't show spinners. Show skeletons:

```
┌──────────────────────────────┐
│ ████░░░░░░░░░░░  (skeleton) │
│ ████████░░░░░░░  (skeleton) │
│ ░░░░░░░░░░░░░░░  (skeleton) │
│                              │
│ Skeleton matches the shape   │
│ of actual content. Fades in  │
│ when data arrives.           │
└──────────────────────────────┘
```

### 5. Error States

API errors should show inline, not modals:

```
┌──────────────────────────────┐
│ ⚠️ Failed to load project    │
│                              │
│ Error: 502 Bad Gateway       │
│                              │
│ [Retry]  [View cached data]  │  ← If we have stale data, offer it
└──────────────────────────────┘
```

## Scroll Performance

The rich active page will have 8+ sections, some with lists. On mobile, this is a scroll performance risk.

**My recommendations:**
- Virtualize the timeline if it has 50+ events (use IntersectionObserver, not a library)
- Lazy-load sections below the fold (don't render Agent details until user scrolls near them)
- Use `will-change: transform` only on animated elements, not everything
- CSS containment: `contain: layout style paint` on each section card
- Debounce SSE updates: batch state changes into 100ms frames, not per-event

**Do NOT use:** React, Vue, Svelte, or any framework. The current vanilla JS + custom state store is fine. The performance comes from avoiding framework overhead, not adding more of it.

## Accessibility Requirements

Non-negotiable for v4:
- All interactive elements must be keyboard-navigable
- Tab bar must use `role="tablist"` / `role="tab"` / `role="tabpanel"`
- Status badges must have text alternatives (not just color)
- `prefers-reduced-motion` must disable all animations
- Focus management: when switching tabs, focus moves to the new tab panel
- ARIA live regions for SSE updates: `aria-live="polite"` on token counter

## My Verdict

The current codebase is ~40% of what's needed. The SSE infrastructure, API layer, and component modularity survive. Everything about layout, state management, and user flows needs to be rebuilt. The "rich active page" is the hard part — not because of the data, but because of the 15+ states you need to design for.

Start with the states, not the pixels. Design the empty state first, then loading, then error, then the happy path. That's how you build something that works in production, not just in a demo.

---

*GLM 5.1 out. UX is not about how it looks. It's about how it works when everything goes wrong.*
