# COUNCIL OPINION — Kimi 2.6 (Architecture)

**Subject:** Viewport Dashboard v4 — Data Model & Information Architecture  
**Date:** 2026-05-30  
**Stance:** The current architecture is structurally broken. A tabbed redesign requires rethinking the data layer from scratch.

---

## The Problem I See

The current implementation has **no concept of project identity**. It treats sandboxes as flat cards with a `name` field. There's no notion of "project lifecycle," no definition of what "active" or "archived" means at the data level, and no way to group related sandboxes under a coherent project umbrella.

The API returns a flat array of trees. The frontend merges two data sources (`/api/v1/tree` and `/api/v1/summary`) in the client, patching holes with `if (!sandboxes[s.name])` guards. This is a **data smell** — the server should be the single source of truth for project classification.

## What's Wrong With the Current Data Flow

1. **No project classification endpoint.** The server doesn't distinguish active vs archived. The frontend would have to implement this logic, which means classification logic lives in the wrong place.

2. **SSE pushes raw summary blobs.** The `summary` event sends all sandbox states. For a tabbed dashboard, you need filtered updates — "here's what changed in the active tab" vs "here's what changed in archived."

3. **No timeline data model.** The detail panel fetches `/api/v1/sandbox/{name}/timeline` but there's no schema. It's just whatever `renderTimeline()` can parse. This makes the "rich active project page" impossible to build reliably.

4. **Token usage is per-sandbox, not per-project.** If "Active" means a project with multiple sandboxes (a production deploy, a staging test, a sandbox), there's no way to roll up token consumption.

## My Opinion: How to Fix It

### 1. Define "Active" and "Archived" Server-Side

```python
# A project is "active" if:
# - Any of its sandboxes has status in (active, spawning, running, working)
# - OR its last activity was < 10 days ago
# - OR it has pending dispatch tasks

# A project is "archived" if:
# - All sandboxes are idle/dead
# - AND last activity was ≥ 10 days ago
# - AND no pending dispatch tasks
```

The classification MUST happen at the API level. Don't push this to the frontend.

### 2. Introduce a Project Entity

The data model needs a `Project` abstraction above sandboxes:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "Project": {
    "type": "object",
    "required": ["id", "name", "status", "sandboxes", "created_at", "last_activity"],
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string" },
      "status": { "type": "string", "enum": ["active", "archived", "idle"] },
      "sandboxes": {
        "type": "array",
        "items": { "$ref": "#/Sandbox" }
      },
      "phase": { "type": "string", "description": "Current lifecycle phase: planning, building, testing, shipping, idle" },
      "agents": {
        "type": "object",
        "properties": {
          "comm": { "$ref": "#/AgentNode" },
          "lead": { "$ref": "#/AgentNode" },
          "arch": { "$ref": "#/AgentNode" },
          "soldiers": { "type": "array", "items": { "$ref": "#/AgentNode" } },
          "verify": { "$ref": "#/AgentNode" }
        }
      },
      "pipeline": {
        "type": "object",
        "properties": {
          "current_phase": { "type": "string" },
          "next_phase": { "type": "string" },
          "steps": { "type": "array", "items": { "$ref": "#/PipelineStep" } },
          "manifest_path": { "type": "string" }
        }
      },
      "tokens": {
        "type": "object",
        "properties": {
          "used": { "type": "integer" },
          "budget": { "type": "integer" },
          "burn_rate": { "type": "number" },
          "history": { "type": "array", "items": { "type": "number" } }
        }
      },
      "issues": {
        "type": "object",
        "properties": {
          "known": { "type": "array", "items": { "$ref": "#/Issue" } },
          "reported_bugs": { "type": "array", "items": { "$ref": "#/Issue" } }
        }
      },
      "timeline": { "type": "array", "items": { "$ref": "#/TimelineEvent" } },
      "git": {
        "type": "object",
        "properties": {
          "branch": { "type": "string" },
          "commit": { "type": "string" },
          "dirty": { "type": "boolean" }
        }
      }
    }
  },
  "Sandbox": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "status": { "type": "string" },
      "model": { "type": "string" },
      "role": { "type": "string", "enum": ["comm", "lead", "arch", "soldier", "verify"] },
      "tokens_used": { "type": "integer" },
      "tokens_budget": { "type": "integer" },
      "current_task": { "type": "string" }
    }
  },
  "AgentNode": {
    "type": "object",
    "properties": {
      "role": { "type": "string" },
      "status": { "type": "string", "enum": ["idle", "active", "working", "error"] },
      "model": { "type": "string" },
      "current_task": { "type": "string" },
      "sandbox": { "type": "string" }
    }
  },
  "PipelineStep": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "status": { "type": "string", "enum": ["pending", "active", "completed", "failed"] },
      "started_at": { "type": "string", "format": "date-time" },
      "completed_at": { "type": "string", "format": "date-time" },
      "duration_ms": { "type": "integer" }
    }
  },
  "TimelineEvent": {
    "type": "object",
    "properties": {
      "timestamp": { "type": "string", "format": "date-time" },
      "type": { "type": "string" },
      "message": { "type": "string" },
      "sandbox": { "type": "string" }
    }
  },
  "Issue": {
    "type": "object",
    "properties": {
      "id": { "type": "string" },
      "title": { "type": "string" },
      "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
      "source": { "type": "string" },
      "reported_at": { "type": "string", "format": "date-time" }
    }
  }
}
```

### 3. New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/projects` | GET | All projects with status classification |
| `/api/v1/projects?status=active` | GET | Active projects only |
| `/api/v1/projects?status=archived` | GET | Archived projects only |
| `/api/v1/projects/{id}` | GET | Full project detail (for the rich Active page) |
| `/api/v1/projects/{id}/timeline` | GET | Project timeline |
| `/api/v1/projects/{id}/issues` | GET | Known issues + reported bugs |
| `/api/v1/events/projects` | GET (SSE) | Filtered SSE for project-level updates |

### 4. SSE Refactoring

The current SSE pushes everything. The v4 SSE should emit:
- `project.status_changed` — when a project transitions active→archived or vice versa
- `project.token_update` — incremental token updates for active projects
- `project.pipeline_step` — pipeline step completions
- `project.agent_update` — agent status changes

This means the frontend can render each tab independently without processing irrelevant updates.

### 5. Information Hierarchy

The "rich active page" needs structured data. Here's my proposed layout hierarchy:

```
PROJECT (active)
├── Header: name, status badge, phase indicator, last activity
├── Overview Row:
│   ├── Token Usage (progress bar + burn rate + estimate)
│   ├── Timeline (horizontal timeline of phases)
│   └── Pipeline State (current step, next step, completion %)
├── Agents Section:
│   ├── COMM node (status, model, current task)
│   ├── LEAD node (status, model, current task)
│   ├── ARCH node (status, model, current task)
│   ├── SOLDIERS (count, status breakdown, individual cards)
│   └── VERIFY node (status, model, current task)
├── Known Issues (expandable list)
├── Reported Bugs (expandable list)
├── Git State (branch, commit, dirty flag)
└── Sandbox Details (sub-cards for each sandbox in this project)
```

### 6. What I'd Kill

- The flat card grid. It's a monitoring dashboard, not a project management tool.
- Client-side classification logic. The server should know what's active.
- Merged data sources. One endpoint per view, one source of truth.
- The detail drawer. For a "literature-grade" active page, a drawer is a toy.

## Tradeoff Assessment

**Speed vs Quality:** I'd spend 2 days on the data model, 1 day on API endpoints, then build the frontend. Getting the data model right first means the frontend writes itself.

**Reuse vs Rewrite:** The `server.py` backend mostly survives. The army tree builder, dispatch parsing, and SSE infrastructure are solid. What dies: the flat-project view and client-side filtering. The frontend is mostly a rewrite — the component architecture is fine but the layout and data flow change completely.

**Risk:** The riskiest part is the classification logic. If "active" vs "archived" is wrong, the whole dashboard misleads. I'd add a `/api/v1/projects/classification` debug endpoint that shows the raw reasoning.

---

*Kimi 2.6 out. The data model is the foundation. Build it right or build it twice.*
