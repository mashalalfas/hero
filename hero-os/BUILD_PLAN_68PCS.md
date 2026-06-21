# HERO OS Dashboard — 68-Piece Build Plan
## Project: HERO OS | Builder: Kimi K2.6 | Stack: FastAPI + Vanilla JS + CSS

### Architecture
- **Backend**: Extend `src/hero/web/server.py` with new endpoints
- **Frontend**: `hero-os/public/index.html` + `hero-os/src/js/` modules + `hero-os/src/styles/main.css`
- **Data**: Reads from `~/.hero/dispatch/*.toon` and existing HERO state
- **Real-time**: SSE (existing infrastructure)

---

## Backend — Server Extensions (server.py)

### Pipeline & Metrics Endpoints
1. `GET /api/v1/pipeline/stages` — Return pipeline stage definitions with current status per sandbox
2. `GET /api/v1/pipeline/active` — Return only currently running pipeline stages
3. `GET /api/v1/agents/active` — Return all active agents across sandboxes with role, model, task
4. `GET /api/v1/agents/{sandbox}` — Return agents for specific sandbox
5. `GET /api/v1/metrics/detailed` — Return enhanced metrics (tokens, budget, tool calls, stages)
6. `GET /api/v1/metrics/health` — Return system health score (0-100)
7. `GET /api/v1/dispatch/queue` — Return pending dispatch tasks
8. `GET /api/v1/dispatch/history` — Return recent completed tasks (last 50)
9. `GET /api/v1/sandboxes` — Return list of all sandboxes with basic info
10. `GET /api/v1/sandbox/{name}/agents` — Return agents for sandbox with detailed status

### Command Execution Endpoints
11. `POST /api/v1/command/spawn` — Spawn new sandbox (extend existing)
12. `POST /api/v1/command/kill` — Kill sandbox (extend existing)
13. `POST /api/v1/command/dispatch` — Create new dispatch task
14. `POST /api/v1/command/approve` — Approve council proposal
15. `POST /api/v1/command/reject` — Reject council proposal
16. `POST /api/v1/command/pipeline/run` — Trigger full pipeline on sandbox
17. `POST /api/v1/command/pipeline/skip` — Skip specific pipeline stage
18. `POST /api/v1/command/architect` — Send task to architect role
19. `POST /api/v1/command/lead` — Send task to lead role
20. `POST /api/v1/command/soldier` — Send task to soldier role

### SSE Enhancements
21. SSE event: `pipeline_update` — Push pipeline stage changes
22. SSE event: `agent_spawned` — Push new agent spawned
23. SSE event: `agent_completed` — Push agent finished
24. SSE event: `dispatch_created` — Push new dispatch task
25. SSE event: `stage_transition` — Push pipeline stage transition
26. SSE event: `error_alert` — Push error/bottleneck alert

---

## Frontend — Core App Shell

### HTML Structure (index.html)
27. Main layout grid: pipeline panel + right sidebar
28. Header with logo, connection status, metrics
29. Pipeline flow container
30. Command center section
31. Agent grid section
32. Dispatch queue section
33. Detail modal structure
34. Toast notification container

### JavaScript — Service Layer
35. `src/js/services/api.js` — HTTP client for all endpoints
36. `src/js/services/sse.js` — SSE connection manager with auto-reconnect
37. `src/js/services/state.js` — Central state store (sandboxes, agents, pipeline)
38. `src/js/services/websocket.js` — Fallback WebSocket if SSE fails

---

## Frontend — Pipeline Visualization

### Pipeline Renderer
39. `src/js/components/PipelineFlow.js` — Main pipeline flow renderer
40. Stage node creation: NAVIGATION, COUNCIL, RESEARCH, PE, ARCHITECT, LEAD, SOLDIERS, PRE-COMMIT, BUILD, HARDEN, LEGAL, CI, VERIFY, ARCHIVE
41. Stage status coloring: idle/running/done/error/bypassed
42. Connector arrows between stages with flow animation
43. Click handler: open stage detail modal
44. Hover effects: glow, tooltip with stage info
45. Zoom controls: zoom in/out/reset for pipeline container
46. Legend: status color key
47. Active pulse animation on running stages
48. Bypass indicator (dashed border, opacity)

---

## Frontend — Agent Grid

49. `src/js/components/AgentGrid.js` — Agent card grid renderer
50. Agent card: role icon, name, model, status dot
51. Status dot animations: running pulse, done solid green, error red
52. Click handler: open agent detail in modal
53. Active agent highlighting (border glow)
54. Empty state: "No active agents" placeholder
55. Auto-refresh on SSE agent events

---

## Frontend — Command Center

56. `src/js/components/CommandCenter.js` — Command form + output
57. Form inputs: sandbox name, task description, model selector, mode selector
58. Spawn button handler: POST to /api/v1/command/spawn
59. Kill button handler: POST to /api/v1/command/kill
60. Output log: real-time command output display with timestamps
61. Loading state: disable button, show spinner
62. Success/error feedback: color-coded log messages

---

## Frontend — Dispatch Queue

63. `src/js/components/DispatchQueue.js` — Queue list renderer
64. Queue item: role icon, description, timestamp
65. Empty state: "No pending tasks"
66. Refresh button handler
67. Auto-update on SSE dispatch events

---

## Frontend — Utilities & Polish

68. `src/js/utils/dom.js` — DOM helpers (escapeHtml, createElement, debounce)
