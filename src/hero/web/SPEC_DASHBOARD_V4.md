# HERO Viewport Dashboard v4 — Specification

## Council Analysis

### Agent 1: Kimi 2.6 — Architecture & Data Model

#### Current State Assessment

The existing HERO Viewport (v3) is a FastAPI + vanilla JS single-page application that:
- Shows all 12 sandboxes in a card grid
- Uses SSE for real-time updates
- Has a detail drawer for individual sandbox inspection
- Relies on 6 API endpoints: `/api/v1/tree`, `/api/v1/summary`, `/api/v1/sandbox/{name}`, `/api/v1/sandbox/{name}/timeline`, `/api/v1/bottlenecks`, `/api/v1/events`

#### Data Model for v4

**Three-View Architecture:**

1. **Overall View** (Current behavior)
   - Data: `/api/v1/tree` + `/api/v1/summary`
   - Shows: All 12 sandboxes in card grid
   - Purpose: Quick status overview

2. **Active View** (New — Full-page dashboard per project)
   - Data: `/api/v1/sandbox/{name}` + `/api/v1/sandbox/{name}/timeline` + `/api/v1/bottlenecks`
   - Shows: Detailed project intelligence
   - Filter: Sandboxes with activity in last 10 days
   - Purpose: Deep project management

3. **Archived View** (New — Simple list)
   - Data: `/api/v1/tree` + `/api/v1/summary`
   - Shows: Projects not touched in 10+ days
   - Purpose: Historical reference

#### Information Hierarchy (Active View)

```
┌─────────────────────────────────────────────────────────────┐
│ ACTIVE VIEW — Full Page Dashboard                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Project Header                                          │
│    - Name, Status Badge, Model, Last Updated               │
├─────────────────────────────────────────────────────────────┤
│ 2. Development Phase                                        │
│    - Current phase (e.g., "Phase 2: Player Controller")   │
│    - Progress bar, Phase description                       │
├─────────────────────────────────────────────────────────────┤
│ 3. Army Hierarchy (Pipeline State)                         │
│    - COMM → LEAD → ARCH → SOLDIERS → VERIFY → ARCHIVIST   │
│    - Visual tree with status indicators                    │
├─────────────────────────────────────────────────────────────┤
│ 4. Agent Activity                                          │
│    - Which agents worked on it (soldiers, council, etc.)   │
│    - Role, Model, Status, Task, Duration                   │
├─────────────────────────────────────────────────────────────┤
│ 5. Token Usage & Budget                                    │
│    - Usage bar, Burn rate, ETA                             │
│    - Per-agent token breakdown                             │
├─────────────────────────────────────────────────────────────┤
│ 6. Recent Activity Timeline                                │
│    - Scrollable event list                                 │
│    - Timestamp, Event type, Details                        │
├─────────────────────────────────────────────────────────────┤
│ 7. Known Issues / Reported Bugs                            │
│    - Issue list from katana.known_issues                   │
│    - Severity, Description, Status                         │
├─────────────────────────────────────────────────────────────┤
│ 8. Next Phase Briefing                                     │
│    - Upcoming phase description                            │
│    - Required resources, Expected duration                 │
├─────────────────────────────────────────────────────────────┤
│ 9. Bottlenecks & Alerts                                    │
│    - Active bottlenecks from /api/v1/bottlenecks           │
│    - Severity, Kind, Suggestion                            │
├─────────────────────────────────────────────────────────────┤
│ 10. Git Status                                             │
│     - Branch, Commit, Status                               │
└─────────────────────────────────────────────────────────────┘
```

#### API Usage Strategy

| View | Primary APIs | Secondary APIs | Polling Interval |
|------|--------------|----------------|------------------|
| Overall | `/api/v1/tree`, `/api/v1/summary` | `/api/v1/events` (SSE) | 10s |
| Active | `/api/v1/sandbox/{name}`, `/api/v1/sandbox/{name}/timeline` | `/api/v1/bottlenecks` | 5s |
| Archived | `/api/v1/tree`, `/api/v1/summary` | None | 30s |

#### Data Enrichment Needs

The current `/api/v1/sandbox/{name}` endpoint returns:
- `status`, `model`, `current_task`, `workdir`
- `tokens_used`, `tokens_budget`, `usage_pct`
- `pipeline_task`, `pipeline_steps`, `pipeline_created`
- `dispatch_tasks`, `errors`, `pending_tasks`, `known_issues`
- `last_compacted` (git summary)

**Missing for v4:**
- Development phase extraction (from pipeline steps or task labels)
- Agent activity breakdown (per-role metrics)
- Token usage per agent (requires dispatch file parsing)
- Next phase briefing (requires pipeline manifest analysis)

---

### Agent 2: GLM 5.1 — Mobile UX & Edge Cases

#### Mobile-First Design Constraints

**Viewport:**
- Target: 375px–428px (iPhone SE to iPhone 14 Pro Max)
- Max-width: 100vw, no horizontal scroll
- Touch targets: ≥44px

**Layout Strategy:**
```
┌─────────────────────────────┐
│ [Overall] [Active] [Archived] │  ← Tab bar (fixed top)
├─────────────────────────────┤
│                              │
│      Content Area            │  ← Scrollable
│      (Full width)            │
│                              │
└─────────────────────────────┘
```

**Active View Mobile Layout:**
```
┌─────────────────────────────┐
│ ← Back    Project Name     │  ← Header
├─────────────────────────────┤
│ Status: Active              │
│ Model: gpt-4o               │
│ Last: 2h ago                │
├─────────────────────────────┤
│ Development Phase           │
│ ████░░░░ Phase 2: 60%      │  ← Progress
├─────────────────────────────┤
│ Pipeline State              │
│ COMM ✓ → LEAD ✓ → ARCH ◉   │  ← Horizontal scroll
│ → SOLDIERS ◉ → VERIFY ○    │
├─────────────────────────────┤
│ Token Budget                │
│ ████░░░░ 45k / 100k (45%)  │
├─────────────────────────────┤
│ Recent Activity             │
│ • 2h ago - soldier-1 done  │  ← Scrollable list
│ • 3h ago - verify started  │
│ • 5h ago - arch completed  │
├─────────────────────────────┤
│ Known Issues (2)            │
│ • [High] Login timeout     │  ← Expandable
│ • [Med] Slow render        │
└─────────────────────────────┘
```

#### States & Edge Cases

**Loading States:**
1. **Initial Load** — Skeleton cards with shimmer animation
2. **Data Fetching** — Progress spinner per section
3. **Empty States** — "No active projects" / "No archived projects"

**Error States:**
1. **API Failure** — Toast notification + retry button
2. **SSE Disconnect** — "Reconnecting..." banner
3. **Sandbox Not Found** — "Project removed" message

**Edge Cases:**
1. **No Sandboxes** — Show empty state with "Deploy an army" CTA
2. **All Archived** — Active view shows "No recent activity"
3. **All Active** — Archived view shows "All projects are active"
4. **Long Project Names** — Truncate with ellipsis, full name on hover/tap
5. **Rapid Status Changes** — Debounce UI updates (250ms)
6. **Network Offline** — Cache last state, show "Offline" indicator

#### Accessibility Requirements

**WCAG 2.1 AA Compliance:**
- Color contrast: ≥4.5:1 for text, ≥3:1 for UI components
- Keyboard navigation: Full tab order, Enter/Space to activate
- Screen reader: ARIA labels, live regions for updates
- Focus management: Focus trap in modals, visible focus rings

**ARIA Structure:**
```html
<nav aria-label="View tabs">
  <button aria-selected="true" aria-controls="panel-overall">Overall</button>
  <button aria-selected="false" aria-controls="panel-active">Active</button>
  <button aria-selected="false" aria-controls="panel-archived">Archived</button>
</nav>

<main aria-live="polite" aria-atomic="true">
  <!-- Dynamic content -->
</main>
```

**Keyboard Shortcuts:**
- `1` / `2` / `3` — Switch views
- `Esc` — Close detail panel
- `←` / `→` — Navigate between projects in Active view
- `↑` / `↓` — Scroll through timeline

#### Touch Interactions

1. **Swipe Left/Right** — Navigate between projects in Active view
2. **Pull to Refresh** — Reload current view data
3. **Long Press** — Show context menu (Kill, Restart, etc.)
4. **Pinch to Zoom** — Disabled (use scroll for detail)

---

### Agent 3: MiMo Pro — UI Component Tree & Implementation Plan

#### Component Architecture

```
src/hero/web/static/js/
├── app.js                    # Entry point, router, state init
├── services/
│   ├── api.js               # API client (existing)
│   ├── sse.js               # SSE manager (existing)
│   ├── state.js             # State management (existing)
│   └── cache.js             # NEW: Client-side cache for offline support
├── components/
│   ├── header.js            # Existing (updated for tabs)
│   ├── tab-bar.js           # NEW: View switcher
│   ├── overall/
│   │   ├── sandbox-grid.js  # Existing (refactored)
│   │   └── stats-bar.js     # Existing (updated)
│   ├── active/
│   │   ├── project-page.js  # NEW: Full-page dashboard
│   │   ├── phase-card.js    # NEW: Development phase display
│   │   ├── pipeline-viz.js  # NEW: Army hierarchy visualization
│   │   ├── agent-list.js    # NEW: Agent activity breakdown
│   │   ├── token-budget.js  # NEW: Token usage with burn rate
│   │   ├── timeline.js      # Existing (enhanced)
│   │   ├── issues-list.js   # NEW: Known issues display
│   │   ├── briefing-card.js # NEW: Next phase briefing
│   │   └── bottlenecks.js   # NEW: Bottleneck alerts
│   ├── archived/
│   │   └── archive-list.js  # NEW: Simple project list
│   └── shared/
│       ├── badge.js         # Existing
│       ├── progress-bar.js  # Existing
│       ├── skeleton.js      # NEW: Loading skeletons
│       └── toast.js         # Existing
└── utils/
    ├── dom.js               # Existing
    └── formatters.js        # NEW: Date/number formatting
```

#### CSS Architecture

```
src/hero/web/static/css/
├── tokens.css               # Existing (updated for new colors)
├── base.css                 # Existing
├── layout.css               # Existing (updated for tabs)
├── components.css           # Existing (updated)
├── animations.css           # Existing
├── tabs.css                 # NEW: Tab bar styles
├── active-view.css          # NEW: Full-page dashboard styles
├── archived-view.css        # NEW: Archive list styles
└── mobile.css               # NEW: Mobile-specific overrides
```

#### Implementation Phases

**Phase 1: Foundation (Days 1-2)**
1. Add tab navigation component
2. Create client-side routing (hash-based)
3. Refactor state management for multi-view
4. Add loading skeleton components

**Phase 2: Overall View (Days 3-4)**
1. Refactor existing sandbox grid
2. Update stats bar with new metrics
3. Add pull-to-refresh
4. Implement offline caching

**Phase 3: Active View (Days 5-8)**
1. Create project page layout
2. Build phase card component
3. Implement pipeline visualization
4. Build agent activity list
5. Create token budget display
6. Enhance timeline component
7. Build issues list
8. Create briefing card
9. Add bottleneck alerts

**Phase 4: Archived View (Days 9-10)**
1. Build archive list component
2. Add restore/reactivate functionality
3. Implement search/filter

**Phase 5: Polish (Days 11-12)**
1. Mobile optimization
2. Accessibility audit
3. Performance optimization
4. Error handling refinement

#### File Changes Required

**Backend (server.py):**
1. Add `/api/v1/sandbox/{name}/detail` endpoint (aggregated data)
2. Add `/api/v1/sandbox/{name}/phase` endpoint (phase extraction)
3. Add `/api/v1/sandbox/{name}/agents` endpoint (agent breakdown)
4. Add `/api/v1/active-sandboxes` endpoint (sandboxes with recent activity)

**Frontend:**
1. Update `index.html` with new structure
2. Add tab navigation to `header.js`
3. Create routing system in `app.js`
4. Add all new components (see component tree)
5. Add new CSS files
6. Update `api.js` with new endpoints

#### Performance Considerations

1. **Lazy Loading** — Load Active view data only when tab selected
2. **Debounced Updates** — 250ms debounce for SSE updates
3. **Virtual Scrolling** — For timeline with 100+ events
4. **Image Optimization** — Use CSS for icons, no raster images
5. **Bundle Size** — Keep vanilla JS, no frameworks (current approach)

#### Testing Strategy

1. **Unit Tests** — Component rendering, data formatting
2. **Integration Tests** — API calls, SSE connections
3. **E2E Tests** — Full user flows (view switching, project selection)
4. **Mobile Tests** — Touch interactions, responsive layout
5. **Accessibility Tests** — Keyboard navigation, screen reader

---

## Final Specification

### 1. Overview

HERO Viewport Dashboard v4 is a mobile-first web application that provides three distinct views for monitoring HERO sandbox projects:

1. **Overall** — Quick status of all 12 sandboxes
2. **Active** — Deep-dive into recently active projects (last 10 days)
3. **Archived** — Simple list of inactive projects

### 2. Architecture

#### 2.1 Technology Stack
- **Backend:** FastAPI (Python) — existing
- **Frontend:** Vanilla JavaScript (ES6 modules) — existing
- **Styling:** CSS Custom Properties + BEM methodology
- **Real-time:** Server-Sent Events (SSE)

#### 2.2 File Structure

```
src/hero/web/
├── server.py                    # FastAPI backend (updated)
├── static/
│   ├── index.html               # Main HTML (updated)
│   ├── css/
│   │   ├── tokens.css           # Design tokens
│   │   ├── base.css             # Reset + base styles
│   │   ├── layout.css           # Grid/flex layouts
│   │   ├── components.css       # Component styles
│   │   ├── animations.css       # Transitions/keyframes
│   │   ├── tabs.css             # NEW: Tab navigation
│   │   ├── active-view.css      # NEW: Full-page dashboard
│   │   ├── archived-view.css    # NEW: Archive list
│   │   └── mobile.css           # NEW: Mobile overrides
│   └── js/
│       ├── app.js               # Entry point + router
│       ├── services/
│       │   ├── api.js           # API client
│       │   ├── sse.js           # SSE manager
│       │   ├── state.js         # State management
│       │   └── cache.js         # NEW: Client cache
│       ├── components/
│       │   ├── header.js        # Header with tabs
│       │   ├── tab-bar.js       # NEW: View switcher
│       │   ├── overall/         # Overall view components
│       │   ├── active/          # Active view components
│       │   ├── archived/        # Archived view components
│       │   └── shared/          # Shared components
│       └── utils/
│           ├── dom.js           # DOM utilities
│           └── formatters.js    # NEW: Formatting utils
└── SPEC_DASHBOARD_V4.md         # This document
```

### 3. Data Model

#### 3.1 API Endpoints

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `/api/v1/tree` | GET | Army hierarchy for all sandboxes | Overall, Archived |
| `/api/v1/summary` | GET | Army metrics aggregate | Overall, Archived |
| `/api/v1/sandbox/{name}` | GET | Detailed sandbox data | Active |
| `/api/v1/sandbox/{name}/timeline` | GET | Event timeline | Active |
| `/api/v1/sandbox/{name}/detail` | GET | **NEW:** Aggregated detail | Active |
| `/api/v1/sandbox/{name}/phase` | GET | **NEW:** Development phase | Active |
| `/api/v1/sandbox/{name}/agents` | GET | **NEW:** Agent breakdown | Active |
| `/api/v1/active-sandboxes` | GET | **NEW:** Recently active list | Active |
| `/api/v1/bottlenecks` | GET | Detected bottlenecks | Active |
| `/api/v1/events` | SSE | Real-time updates | All views |

#### 3.2 State Management

```javascript
{
  // View state
  currentView: 'overall' | 'active' | 'archived',
  selectedProject: string | null,
  
  // Data
  sandboxes: { [name: string]: SandboxData },
  activeProjects: string[],
  archivedProjects: string[],
  
  // UI state
  isLoading: boolean,
  isConnected: boolean,
  error: string | null,
  
  // Cache
  cache: { [key: string]: { data: any, timestamp: number } }
}
```

### 4. Component Specifications

#### 4.1 Tab Bar Component

**Purpose:** Switch between Overall, Active, and Archived views

**Props:**
- `currentView: string` — Active view identifier
- `onViewChange: (view: string) => void` — Callback

**States:**
- Default: Three tabs with icons + labels
- Mobile: Fixed bottom bar with icons only
- Active: Highlighted tab with accent color

**Accessibility:**
- `role="tablist"` on container
- `role="tab"` on each tab
- `aria-selected` for active tab
- Keyboard: Arrow keys to navigate, Enter to select

#### 4.2 Active View — Project Page

**Purpose:** Full-page dashboard for a single project

**Layout:**
```
┌─────────────────────────────────────────┐
│ ← Back        Project Name        ⋮    │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Phase Card                      │   │
│  │ Phase 2: Player Controller      │   │
│  │ ████████░░░░░░ 60%              │   │
│  │ "Building core movement..."     │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Pipeline State                  │   │
│  │ COMM ✓ → LEAD ✓ → ARCH ◉       │   │
│  │ → SOLDIERS ◉ → VERIFY ○        │   │
│  │ → ARCHIVIST ○                   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Agent Activity                  │   │
│  │ • soldier-1: gpt-4o (active)   │   │
│  │ • soldier-2: claude-3 (done)   │   │
│  │ • verify-1: gpt-4o (pending)   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Token Budget                    │   │
│  │ ████░░░░ 45k / 100k (45%)      │   │
│  │ Burn: 2.5k/min | ETA: 22 min   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Recent Activity                 │   │
│  │ • 2h ago — soldier-1 completed  │   │
│  │ • 3h ago — verify started       │   │
│  │ • 5h ago — arch deployed        │   │
│  │ [View all 47 events →]          │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Known Issues (2)                │   │
│  │ ▸ [High] Login timeout          │   │
│  │ ▸ [Med] Slow render             │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Next Phase Briefing             │   │
│  │ Phase 3: Combat System          │   │
│  │ "Implement enemy AI..."         │   │
│  │ Est: 3 days | Tokens: 25k       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Bottlenecks                     │   │
│  │ ⚠ Token choke: 62% of budget   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Git Status                      │   │
│  │ Branch: feature/combat          │   │
│  │ Commit: a1b2c3d                 │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

**Sub-components:**

1. **Phase Card**
   - Shows current development phase
   - Progress bar with percentage
   - Phase description text
   - Data source: Pipeline steps or task labels

2. **Pipeline Visualization**
   - Horizontal scrollable chain
   - Status indicators: ✓ (done), ◉ (active), ○ (pending)
   - Role labels with colors
   - Data source: `/api/v1/sandbox/{name}` → `pipeline_steps`

3. **Agent Activity List**
   - Role, Model, Status, Task
   - Expandable for details
   - Data source: `/api/v1/sandbox/{name}` → `dispatch_tasks`

4. **Token Budget**
   - Progress bar with usage percentage
   - Burn rate (tokens/minute)
   - ETA to exhaustion
   - Data source: `/api/v1/sandbox/{name}` → `tokens_used`, `tokens_budget`

5. **Timeline**
   - Scrollable event list
   - Timestamp, Event type, Details
   - "View all" link for full timeline
   - Data source: `/api/v1/sandbox/{name}/timeline`

6. **Issues List**
   - Expandable items with severity
   - Data source: `/api/v1/sandbox/{name}` → `known_issues`

7. **Briefing Card**
   - Next phase description
   - Required resources
   - Expected duration
   - Data source: Pipeline manifest analysis

8. **Bottlenecks**
   - Alert cards with severity
   - Data source: `/api/v1/bottlenecks`

#### 4.3 Archived View

**Purpose:** Simple list of inactive projects

**Layout:**
```
┌─────────────────────────────────────────┐
│ Archived Projects (5)                   │
├─────────────────────────────────────────┤
│ 🔍 Search...                            │
├─────────────────────────────────────────┤
│ • project-alpha                         │
│   Last active: 15 days ago              │
│   Tokens: 12k / 50k                     │
│                                         │
│ • project-beta                          │
│   Last active: 22 days ago              │
│   Tokens: 8k / 50k                      │
│                                         │
│ • project-gamma                         │
│   Last active: 30 days ago              │
│   Tokens: 45k / 50k                     │
└─────────────────────────────────────────┘
```

**Features:**
- Search/filter by name
- Sort by last active, token usage
- Tap to view full details (opens Active view)
- "Restore" action to move back to Active

### 5. Mobile UX Specifications

#### 5.1 Viewport & Breakpoints

```css
/* Mobile first */
:root {
  --viewport-mobile: 375px;
  --viewport-tablet: 768px;
  --viewport-desktop: 1024px;
}

/* Breakpoints */
@media (min-width: 768px) { /* Tablet */ }
@media (min-width: 1024px) { /* Desktop */ }
```

#### 5.2 Touch Targets

- Minimum: 44px × 44px
- Recommended: 48px × 48px
- Spacing between targets: 8px minimum

#### 5.3 Mobile Layout Rules

1. **Tab Bar:** Fixed bottom on mobile, fixed top on desktop
2. **Content:** Full width, padding: 16px
3. **Cards:** Stack vertically, no side-by-side
4. **Pipeline:** Horizontal scroll with snap
5. **Timeline:** Virtual scroll for performance
6. **Modals:** Full-screen on mobile, centered on desktop

#### 5.4 Gesture Support

| Gesture | Action | View |
|---------|--------|------|
| Swipe Left | Next project | Active |
| Swipe Right | Previous project | Active |
| Pull Down | Refresh | All |
| Long Press | Context menu | All |
| Pinch | Disabled | - |

### 6. Accessibility Specifications

#### 6.1 WCAG 2.1 AA Compliance

- **Color Contrast:** ≥4.5:1 for text, ≥3:1 for UI
- **Keyboard Navigation:** Full tab order
- **Screen Reader:** ARIA labels, live regions
- **Focus Management:** Visible focus rings, focus traps

#### 6.2 ARIA Structure

```html
<!-- Tab navigation -->
<nav aria-label="Dashboard views">
  <div role="tablist">
    <button role="tab" aria-selected="true" aria-controls="panel-overall">
      Overall
    </button>
    <button role="tab" aria-selected="false" aria-controls="panel-active">
      Active
    </button>
    <button role="tab" aria-selected="false" aria-controls="panel-archived">
      Archived
    </button>
  </div>
</nav>

<!-- View panels -->
<main>
  <section id="panel-overall" role="tabpanel" aria-labelledby="tab-overall">
    <!-- Overall view content -->
  </section>
  
  <section id="panel-active" role="tabpanel" aria-labelledby="tab-active" hidden>
    <!-- Active view content -->
  </section>
  
  <section id="panel-archived" role="tabpanel" aria-labelledby="tab-archived" hidden>
    <!-- Archived view content -->
  </section>
</main>

<!-- Live region for updates -->
<div aria-live="polite" aria-atomic="true" class="sr-only">
  <!-- Dynamic status updates -->
</div>
```

#### 6.3 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Switch to Overall view |
| `2` | Switch to Active view |
| `3` | Switch to Archived view |
| `Esc` | Close detail panel / modal |
| `←` | Previous project (Active view) |
| `→` | Next project (Active view) |
| `↑` | Scroll up |
| `↓` | Scroll down |
| `Enter` | Activate focused element |
| `Space` | Toggle expanded section |

### 7. Performance Requirements

#### 7.1 Load Times

- **Initial Load:** < 2s on 3G
- **View Switch:** < 100ms
- **Data Refresh:** < 500ms

#### 7.2 Optimization Strategies

1. **Lazy Loading:** Load Active view data only when tab selected
2. **Debouncing:** 250ms debounce for SSE updates
3. **Virtual Scrolling:** For timelines with 100+ events
4. **Caching:** Client-side cache with 5-minute TTL
5. **Compression:** Gzip for API responses

#### 7.3 Memory Management

- Unsubscribe from SSE on view change
- Clean up DOM references on component destroy
- Limit cache size (max 50 entries)

### 8. Error Handling

#### 8.1 Error States

| Error | UI Response |
|-------|-------------|
| API Failure | Toast notification + retry button |
| SSE Disconnect | "Reconnecting..." banner |
| Sandbox Not Found | "Project removed" message |
| Network Offline | Cache last state + "Offline" indicator |
| Invalid Data | Graceful degradation, hide affected section |

#### 8.2 Retry Logic

- **API Calls:** Exponential backoff (1s, 2s, 4s, 8s)
- **SSE:** Auto-reconnect with 5s delay
- **Manual Retry:** Button in error states

### 9. Testing Strategy

#### 9.1 Unit Tests

- Component rendering
- Data formatting utilities
- State management logic
- API client functions

#### 9.2 Integration Tests

- API endpoint responses
- SSE connection handling
- View switching logic
- Data flow from API to UI

#### 9.3 E2E Tests

- Full user flows (view switching, project selection)
- Mobile touch interactions
- Keyboard navigation
- Error recovery scenarios

#### 9.4 Performance Tests

- Load time benchmarks
- Memory leak detection
- SSE connection stability
- Scroll performance

### 10. Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Foundation | Days 1-2 | Tab navigation, routing, state management |
| Overall View | Days 3-4 | Refactored grid, stats bar, pull-to-refresh |
| Active View | Days 5-8 | All sub-components (phase, pipeline, agents, etc.) |
| Archived View | Days 9-10 | Archive list, search, restore |
| Polish | Days 11-12 | Mobile optimization, accessibility, performance |

**Total:** 12 working days

### 11. Success Metrics

1. **Mobile Usability:** 100% touch target compliance
2. **Performance:** < 2s load time on 3G
3. **Accessibility:** WCAG 2.1 AA certification
4. **User Satisfaction:** Reduced time to project status (target: < 5s)
5. **Error Rate:** < 1% unhandled errors

### 12. Open Questions

1. **Phase Extraction:** How to determine current phase from pipeline data?
2. **Next Phase Briefing:** Source for upcoming phase description?
3. **Token Burn Rate:** Calculation methodology (rolling average vs. instantaneous)?
4. **Archive Threshold:** Confirm 10 days for archive?
5. **Offline Support:** How long to cache data? (Recommended: 5 minutes)

---

## Appendix A: API Response Examples

### `/api/v1/sandbox/{name}/detail`

```json
{
  "name": "galaxy_oblivion",
  "status": "active",
  "model": "gpt-4o",
  "current_task": "Phase 2: Player Controller",
  "workdir": "/home/max/Development/galaxy_oblivion",
  "tokens_used": 45000,
  "tokens_budget": 100000,
  "usage_pct": 0.45,
  "compactions_used": 3,
  "tool_calls": 127,
  "subagent_count": 4,
  "no_progress_counter": 0,
  "pipeline_task": "Build 3D platformer game",
  "pipeline_steps": {
    "COMM": {"status": "done", "duration": "2m"},
    "LEAD": {"status": "done", "duration": "5m"},
    "ARCH": {"status": "active", "duration": "15m"},
    "SOLDIERS": {"status": "active", "duration": "1h"},
    "VERIFY": {"status": "pending", "duration": null},
    "ARCHIVIST": {"status": "pending", "duration": null}
  },
  "pipeline_created": "2026-05-28T10:00:00Z",
  "dispatch_tasks": [
    {
      "task_id": "sol-001",
      "label": "Player movement controller",
      "model": "gpt-4o",
      "role": "SOLDIER",
      "status": "active",
      "task": "Implement WASD movement with physics",
      "created_at": "2026-05-28T10:15:00Z",
      "completed_at": null,
      "budget": 25000,
      "max_tokens": 25000
    }
  ],
  "errors": [],
  "pending_tasks": ["Enemy AI behavior tree"],
  "known_issues": [
    "Player clips through walls at high speed",
    "Jump height inconsistent on slopes"
  ],
  "last_compacted": "Branch: feature/player-controller\nCommit: a1b2c3d\nStatus: Clean"
}
```

### `/api/v1/sandbox/{name}/phase`

```json
{
  "name": "galaxy_oblivion",
  "current_phase": 2,
  "phase_name": "Player Controller",
  "phase_description": "Implement core player movement, physics, and controls",
  "progress_pct": 60,
  "next_phase": {
    "name": "Combat System",
    "description": "Enemy AI, combat mechanics, damage system",
    "estimated_duration": "3 days",
    "estimated_tokens": 25000
  }
}
```

### `/api/v1/sandbox/{name}/agents`

```json
{
  "name": "galaxy_oblivion",
  "agents": [
    {
      "role": "COMM",
      "count": 1,
      "status": "done",
      "tokens_used": 2000,
      "tasks_completed": 1
    },
    {
      "role": "LEAD",
      "count": 1,
      "status": "done",
      "tokens_used": 5000,
      "tasks_completed": 1
    },
    {
      "role": "ARCH",
      "count": 1,
      "status": "active",
      "tokens_used": 8000,
      "tasks_completed": 0
    },
    {
      "role": "SOLDIER",
      "count": 3,
      "status": "active",
      "tokens_used": 25000,
      "tasks_completed": 2
    },
    {
      "role": "VERIFY",
      "count": 1,
      "status": "pending",
      "tokens_used": 0,
      "tasks_completed": 0
    }
  ],
  "total_tokens_used": 40000,
  "burn_rate": 2500,
  "eta_minutes": 24
}
```

---

## Appendix B: Component Props & Events

### TabBar

```javascript
// Props
{
  currentView: 'overall' | 'active' | 'archived',
  onViewChange: (view: string) => void
}

// Events
'view-change' → { detail: { view: string } }
```

### ProjectPage

```javascript
// Props
{
  projectName: string,
  onBack: () => void,
  onRefresh: () => void
}

// Events
'project-loaded' → { detail: { data: SandboxDetail } }
'project-error' → { detail: { error: Error } }
```

### PhaseCard

```javascript
// Props
{
  phase: number,
  name: string,
  description: string,
  progress: number, // 0-100
  nextPhase?: {
    name: string,
    description: string,
    estimatedDuration: string,
    estimatedTokens: number
  }
}
```

### PipelineViz

```javascript
// Props
{
  steps: {
    [role: string]: {
      status: 'done' | 'active' | 'pending',
      duration: string | null
    }
  }
}
```

### AgentList

```javascript
// Props
{
  agents: Array<{
    role: string,
    count: number,
    status: string,
    tokensUsed: number,
    tasksCompleted: number
  }>
}
```

### TokenBudget

```javascript
// Props
{
  used: number,
  budget: number,
  burnRate: number, // tokens per minute
  etaMinutes: number | null
}
```

---

*Document Version: 1.0*
*Last Updated: 2026-05-30*
*Authors: Kimi 2.6, GLM 5.1, MiMo Pro (Council)*
