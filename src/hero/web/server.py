"""hero.web.server — FastAPI + SSE live dashboard for HERO viewport.

Start with: hero viewport --mode web
Access at: http://localhost:8765
External access: tailscale funnel 8765 or cloudflare tunnel
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from hero.viewport.intel import collect_sandbox_detail, detect_bottlenecks
from hero.state.cache import default_cache
from hero.viewport.metrics import collect
from hero.viewport.tree import _load_dispatch_files, _load_pipeline_manifest, _parse_viewport_toon

DISPATCH_DIR = Path.home() / ".hero" / "dispatch"

# File watcher state for dispatch directory auto-refresh
_dispatch_watch_mtimes: dict[str, float] = {}
_dispatch_watch_changed: bool = False

logger = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="HERO Viewport")

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ──────────────────────────────────────────────────────
if STATIC_DIR.exists():
    # Serve static files with no-cache headers to prevent stale JS/CSS on mobile
    from starlette.staticfiles import StaticFiles as _StaticFiles
    class _NoCacheStaticFiles(_StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            if path.endswith(('.js', '.css', '.html')):
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            return response
    app.mount("/static", _NoCacheStaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Dispatch file watcher ─────────────────────────────────────────────────
@app.on_event("startup")
async def _startup_watch_dispatch():
    """Start background file watcher for dispatch directory changes."""
    asyncio.create_task(_watch_dispatch_dir())
    asyncio.create_task(_cleanup_stale_dispatches())


async def _cleanup_stale_dispatches():
    """Clean stale dispatch files for dead/inactive sandboxes.

    Runs once at startup, then every 30 minutes.
    Removes dispatch dirs for sandboxes no longer active in INDEX.toon
    and dispatch entries older than 24h for completed sandboxes.
    """
    import time
    INDEX = Path.home() / ".hero" / "sandboxes" / "INDEX.toon"

    while True:
        try:
            # Get active sandbox names from INDEX.toon
            active = set()
            dead = set()
            if INDEX.exists():
                text = INDEX.read_text()
                for m in re.finditer(r'{name: "([^"]+)".*?status: "([^"]+)"', text):
                    name = m.group(1)
                    status = m.group(2)
                    if status in ("active", "spawning"):
                        active.add(name)
                    else:
                        dead.add(name)

            # Remove dispatch dirs for dead sandboxes (in INDEX but not active)
            if DISPATCH_DIR.exists():
                for d in DISPATCH_DIR.iterdir():
                    if d.is_dir():
                        if d.name not in active:
                            logger.info(f"Cleaning dispatch for dead sandbox: {d.name}")
                            shutil.rmtree(d, ignore_errors=True)

            # Also clean .toon files with no active sandbox
            for f in DISPATCH_DIR.glob("*.toon"):
                try:
                    data = _parse_viewport_toon(f.read_text())
                    if data and data.get("sandbox") not in active:
                        f.unlink(missing_ok=True)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"dispatch cleanup error: {e}")

        await asyncio.sleep(1800)  # 30 minutes


async def _watch_dispatch_dir():
    """Poll ~/.hero/dispatch/ every 5 seconds for changes, flag for SSE."""
    global _dispatch_watch_mtimes, _dispatch_watch_changed
    while True:
        await asyncio.sleep(5)
        if not DISPATCH_DIR.exists():
            continue
        current: dict[str, float] = {}
        try:
            for f in DISPATCH_DIR.iterdir():
                if f.is_file():
                    current[f.name] = f.stat().st_mtime
        except OSError:
            continue
        changed = False
        # Check for new or modified files
        for name, mtime in current.items():
            prev = _dispatch_watch_mtimes.get(name)
            if prev is None or prev != mtime:
                changed = True
                break
        if not changed:
            # Check for deleted files
            for name in _dispatch_watch_mtimes:
                if name not in current:
                    changed = True
                    break
        _dispatch_watch_mtimes = current
        if changed:
            _dispatch_watch_changed = True
            logger.info("dispatch directory changed — tree_update queued")


# ── Auth ──────────────────────────────────────────────────────────────────
def _check_auth(request: Request) -> None:
    """Check bearer token if HERO_WEB_TOKEN is set."""
    token = os.environ.get("HERO_WEB_TOKEN")
    if not token:
        return  # No token configured — open access
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid or missing token")


# ── Routes ────────────────────────────────────────────────────────────────


def _build_army_tree(name: str, status: str, model: str | None = None,
                     current_task: str | None = None,
                     tokens_used: int = 0, tokens_budget: int = 0,
                     tool_calls: int = 0) -> dict:
    """Build the HERO army hierarchy tree for one sandbox.

    Shows the standard command structure:
      COMM -> LEAD -> ARCH + SOLDIERS + VERIFY

    Populates actual role statuses from dispatch files when available.
    """
    # Try to read dispatch data for this sandbox
    dispatch_roles: dict[str, list[dict]] = defaultdict(list)

    # Read TOON files from flat ~/.hero/dispatch/*.toon
    for f in sorted(DISPATCH_DIR.glob("*.toon")):
        try:
            data = _parse_viewport_toon(f.read_text())
            if data and data.get("sandbox") == name:
                role = (data.get("role") or "SOLDIER").upper()
                dispatch_roles[role].append(data)
        except Exception:
            pass

    # Read JSON files from ~/.hero/dispatch/<sandbox>/*.json
    sb_dir = DISPATCH_DIR / name
    if sb_dir.exists():
        for f in sorted(sb_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                role = (data.get("role") or "SOLDIER").upper()
                dispatch_roles[role].append(data)
            except (json.JSONDecodeError, OSError):
                pass

    # Status colors for roles
    GREEN = "#22c55e"
    YELLOW = "#eab308"
    RED = "#ef4444"
    BLUE = "#3b82f6"
    GREY = "#64748b"
    CYAN = "#06b6d4"
    PURPLE = "#a855f7"

    def _role_status(role: str) -> tuple[str, str]:
        entries = dispatch_roles.get(role, [])
        if entries:
            latest = max(entries, key=lambda e: float(e.get("last_updated", 0) or 0))
            st = (latest.get("status") or "dispatched").lower()
            if st in ("running", "active", "working"):
                return st, GREEN
            if st in ("done", "completed", "success"):
                return "done", BLUE
            if st in ("error", "failed", "timeout"):
                return st, RED
            if st in ("queued", "pending", "dispatched"):
                return st, YELLOW
            return st, CYAN
        return "pending", GREY

    def _role_model(role: str) -> str | None:
        entries = dispatch_roles.get(role, [])
        if entries:
            latest = max(entries, key=lambda e: float(e.get("last_updated", 0) or 0))
            m = latest.get("model")
            if m:
                return m.split("/")[-1] if "/" in m else m
        return None

    def _role_task(role: str) -> str | None:
        entries = dispatch_roles.get(role, [])
        if entries:
            latest = max(entries, key=lambda e: float(e.get("last_updated", 0) or 0))
            return latest.get("label") or latest.get("task")
        return None

    def _node(role: str, label: str, st: str, color: str,
              mod: str | None = None, tsk: str | None = None,
              children: list | None = None) -> dict:
        return {
            "role": role,
            "label": label,
            "status": st,
            "color": color,
            "model": mod,
            "task": tsk,
            "children": children or [],
        }

    # Build soldier nodes
    soldiers = []
    sol_entries = dispatch_roles.get("SOLDIER", [])
    if sol_entries:
        for i, e in enumerate(sol_entries):
            st = (e.get("status") or "dispatched").lower()
            sc = GREEN if st in ("running","active","working","done") else \
                 YELLOW if st in ("queued","pending","dispatched") else \
                 RED if st in ("error","failed","timeout") else GREY
            mod = e.get("model","").split("/")[-1] if e.get("model") else None
            soldiers.append(_node(
                "SOLDIER", f"soldier-{i+1}", st, sc,
                mod=mod,
                tsk=e.get("label") or e.get("task"),
            ))

    verifiers = []
    ver_entries = dispatch_roles.get("VERIFY", [])
    if ver_entries:
        for i, e in enumerate(ver_entries):
            st = (e.get("status") or "dispatched").lower()
            sc = GREEN if st in ("running","active","working","done") else \
                 YELLOW if st in ("queued","pending","dispatched") else \
                 RED if st in ("error","failed","timeout") else GREY
            verifiers.append(_node("VERIFY", f"verify-{i+1}", st, sc,
                                   tsk=e.get("label") or e.get("task")))

    # Lead status from dispatch
    lead_st, lead_color = _role_status("LEAD")
    lead_model = _role_model("LEAD")
    lead_task = _role_task("LEAD")

    arch_st, arch_color = _role_status("ARCH")
    arch_model = _role_model("ARCH")
    arch_task = _role_task("ARCH")

    # Build the hierarchy
    # COMM -> LEAD -> {ARCH -> SOLDIERS + VERIFY}
    comm_status = status.lower()
    comm_color = GREEN if comm_status in ("active","running","working") else \
                 YELLOW if comm_status in ("dispatched","spawning","booting") else \
                 RED if comm_status in ("error","failed","dead","timeout") else \
                 BLUE if comm_status == "idle" else GREY

    comm = _node("COMM", name, comm_status, comm_color,
                 mod=model.split("/")[-1] if model else None,
                 tsk=current_task)

    arch_node = _node("ARCH", f"{name}-arch", arch_st, arch_color,
                      mod=arch_model, tsk=arch_task,
                      children=soldiers + verifiers)

    lead = _node("LEAD", f"{name}-lead", lead_st, lead_color,
                 mod=lead_model, tsk=lead_task,
                 children=[arch_node] if soldiers or verifiers or arch_st != "pending" else [])

    comm["children"] = [lead] if lead_st != "pending" or soldiers else []

    return comm


@app.get("/api/v1/tree")
async def api_tree(request: Request) -> JSONResponse:
    """Return army hierarchy tree for all sandboxes."""
    _check_auth(request)
    try:
        metrics = collect()
        trees = []
        for s in metrics.sandboxes:
            if not s.name:
                continue
            # Include all sandboxes, even dead/idle — frontend handles display logic
            # Filter only: sandboxes with no name
            if not s.name:
                continue
            tree = _build_army_tree(
                name=s.name,
                status=s.status or "idle",
                model=s.model,
                current_task=s.current_task,
                tokens_used=s.tokens_used or 0,
                tokens_budget=s.tokens_budget or 0,
                tool_calls=s.tool_calls or 0,
            )
            trees.append({
                "sandbox": s.name,
                "status": s.status or "idle",
                "model": (s.model or "").split("/")[-1] if s.model else None,
                "tokens_used": s.tokens_used or 0,
                "tokens_budget": s.tokens_budget or 0,
                "tool_calls": s.tool_calls or 0,
                "tree": tree,
            })
        return JSONResponse({"trees": trees})
    except Exception as exc:
        logger.exception("tree failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/summary")
async def api_summary(request: Request) -> JSONResponse:
    """Return ArmyMetrics JSON for all sandboxes."""
    _check_auth(request)
    try:
        metrics = collect()
        return JSONResponse(_serialize(metrics))
    except Exception as exc:
        logger.exception("summary failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/sandbox/{name}")
async def api_sandbox(name: str, request: Request) -> JSONResponse:
    """Return detailed data for one sandbox."""
    _check_auth(request)
    try:
        detail = collect_sandbox_detail(name)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Sandbox '{name}' not found")
        return JSONResponse(_serialize(detail))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"sandbox detail failed: {name}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/sandbox/{name}/timeline")
async def api_sandbox_timeline(name: str, request: Request) -> JSONResponse:
    """Return event timeline for a sandbox."""
    _check_auth(request)
    try:
        files = _load_dispatch_files(name)
        events = []
        for tid, data in files.items():
            ts = data.get("last_updated") or data.get("created_at")
            if ts:
                events.append({
                    "timestamp": str(ts),
                    "event_type": "dispatch",
                    "task_id": tid,
                    "role": data.get("role", ""),
                    "status": data.get("status", "unknown"),
                    "details": data.get("label") or data.get("task", "")[:60],
                })
        events.sort(key=lambda e: str(e["timestamp"]), reverse=True)
        return JSONResponse(events[:50])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/sandbox/{name}/kill")
async def api_kill_sandbox(name: str, request: Request) -> JSONResponse:
    """Kill a sandbox via CLI."""
    _check_auth(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required")
    confirmation_token = body.get("confirmation_token")
    if not confirmation_token:
        raise HTTPException(status_code=400, detail="confirmation_token required")
    if confirmation_token != name:
        raise HTTPException(status_code=400, detail="confirmation_token must match sandbox name")

    import subprocess
    try:
        result = subprocess.run(
            ["hero", "kill", name, "--force"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Kill command failed"
            raise HTTPException(status_code=500, detail=error_msg)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="hero CLI not found in PATH")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Kill command timed out")

    logger.info(f"Sandbox '{name}' killed successfully")
    return JSONResponse({"status": "killed", "sandbox": name, "message": f"Sandbox '{name}' has been terminated"})


@app.post("/api/v1/sandbox/{name}/spawn")
async def api_spawn_sandbox(name: str, request: Request) -> JSONResponse:
    """Spawn a sandbox via CLI."""
    _check_auth(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required")
    task = body.get("task", "")
    model = body.get("model", "")

    import subprocess
    try:
        cmd = ["hero", "spawn", "--sandbox", name]
        if task:
            cmd.extend(["--task", task])
        if model:
            cmd.extend(["--model", model])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Spawn failed"
            raise HTTPException(status_code=500, detail=error_msg)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="hero CLI not found")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Spawn command timed out")

    logger.info(f"Sandbox '{name}' spawn initiated")
    return JSONResponse({"status": "spawned", "sandbox": name, "message": f"Sandbox '{name}' spawn initiated"})


@app.get("/api/v1/bottlenecks")
async def api_bottlenecks(request: Request) -> JSONResponse:
    """Return detected bottlenecks across all sandboxes."""
    _check_auth(request)
    try:
        bottlenecks = detect_bottlenecks()
        return JSONResponse([_serialize(b) for b in bottlenecks])
    except Exception as exc:
        logger.exception("bottlenecks failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/events")
async def api_events(request: Request) -> EventSourceResponse:
    """SSE endpoint pushing summary every 2s + tree_update on dispatch changes."""
    _check_auth(request)

    async def event_generator():
        global _dispatch_watch_changed
        while True:
            try:
                metrics = collect()
                yield {"event": "summary", "data": json.dumps(_serialize(metrics), default=str)}
                if _dispatch_watch_changed:
                    _dispatch_watch_changed = False
                    yield {"event": "tree_update", "data": "{}"}
            except Exception as exc:
                yield {"event": "error", "data": str(exc)}
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@app.get("/", response_model=None)
async def index(request: Request):
    """Single-page dashboard (serves static/index.html)."""
    _check_auth(request)
    static_index = STATIC_DIR / "index.html"
    if static_index.exists():
        return FileResponse(str(static_index))
    return HTMLResponse(_DASHBOARD_HTML)


# ── Serialization helpers ────────────────────────────────────────────────


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses and non-serializable types to dicts/strings."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f: _serialize(getattr(obj, f)) for f in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if not isinstance(obj, (str, int, float, bool, type(None))):
        return str(obj)
    return obj


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HERO Viewport</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0e17;
  --surface: #111827;
  --surface2: #1a2332;
  --border: #1e293b;
  --text: #e2e8f0;
  --text2: #94a3b8;
  --text3: #64748b;
  --accent: #3b82f6;
  --accent2: #60a5fa;
  --green: #22c55e;
  --green-bg: rgba(34,197,94,0.12);
  --yellow: #eab308;
  --yellow-bg: rgba(234,179,8,0.12);
  --red: #ef4444;
  --red-bg: rgba(239,68,68,0.12);
  --blue: #3b82f6;
  --blue-bg: rgba(59,130,246,0.12);
  --grey: #64748b;
  --grey-bg: rgba(100,116,139,0.12);
  --radius: 12px;
  --radius-sm: 8px;
  --radius-xs: 6px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.header h1 {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.header .logo { font-size: 28px; }

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  display: inline-block;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Stats row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  transition: border-color 0.2s;
}

.stat-card:hover { border-color: var(--text3); }

.stat-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text3);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

.stat-sub {
  font-size: 12px;
  color: var(--text2);
  margin-top: 2px;
}

/* Sandbox cards */
.sandbox-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.sandbox-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.15s;
}

.sandbox-card:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.sandbox-card:active { transform: translateY(0); }

.card-header {
  padding: 14px 16px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.badge-green { background: var(--green-bg); color: var(--green); }
.badge-yellow { background: var(--yellow-bg); color: var(--yellow); }
.badge-red { background: var(--red-bg); color: var(--red); }
.badge-blue { background: var(--blue-bg); color: var(--blue); }
.badge-grey { background: var(--grey-bg); color: var(--grey); }

.model-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  background: rgba(168,85,247,0.15);
  color: #a855f7;
  border: 1px solid rgba(168,85,247,0.25);
  white-space: nowrap;
}

.card-body { padding: 12px 16px 16px; }

/* Tree */
.tree { font-size: 13px; }

.tree-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 3px 0;
  position: relative;
}

.tree-line .branch {
  color: var(--text3);
  font-family: monospace;
  font-size: 14px;
  line-height: 1.4;
  user-select: none;
  white-space: pre;
  flex-shrink: 0;
}

.tree-content {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-height: 20px;
}

.role-icon { font-size: 13px; }
.role-name {
  font-weight: 600;
  font-size: 12px;
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.task-text {
  font-size: 12px;
  color: var(--text2);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .task-text { max-width: 160px; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(4px);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.modal-overlay.show { display: flex; }

.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  width: 100%;
  max-width: 640px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modalIn 0.2s ease;
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.modal-header {
  padding: 14px 16px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.modal-header h3 {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text2);
  font-size: 20px;
  cursor: pointer;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xs);
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: var(--border);
  color: var(--text);
}

.modal-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.modal-body pre {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
}

.loading {
  color: var(--text3);
  font-size: 13px;
  padding: 24px 0;
  text-align: center;
}

.error {
  color: var(--red);
  font-size: 13px;
  padding: 16px;
  background: var(--red-bg);
  border-radius: var(--radius-sm);
}

.empty {
  text-align: center;
  padding: 48px 16px;
  color: var(--text3);
  font-size: 14px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text3); }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1><span class="logo">⚡</span> HERO Viewport</h1>
    <div style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text3);">
      <span class="status-dot"></span> Live
    </div>
  </div>

  <div class="stats-row" id="stats">
    <div class="stat-card">
      <div class="stat-label">Tokens Used</div>
      <div class="stat-value" id="stat-tokens">—</div>
      <div class="stat-sub" id="stat-tokens-sub">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Active Sandboxes</div>
      <div class="stat-value" id="stat-sandboxes">—</div>
      <div class="stat-sub" id="stat-sandboxes-sub">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Tool Calls</div>
      <div class="stat-value" id="stat-tools">—</div>
      <div class="stat-sub" id="stat-tools-sub">—</div>
    </div>
  </div>

  <div class="sandbox-grid" id="trees"></div>
  <div class="empty" id="empty" style="display:none">No active sandboxes.</div>
</div>

<!-- Modal -->
<div class="modal-overlay" id="modal" onclick="closeModal(event)">
  <div class="modal" onclick="event.stopPropagation()">
    <div class="modal-header">
      <h3><span id="modal-icon">⚡</span> <span id="modal-title">Sandbox</span></h3>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body" id="modal-body">
      <div class="loading">Loading...</div>
    </div>
  </div>
</div>

<script>
(function() {
  'use strict';

  const ROLE_ICONS = {
    COMM: '⚡', LEAD: '🎯', ARCH: '🏗️', SOLDIER: '🤖', VERIFY: '🔍', ARCHIVE: '📦'
  };

  const STATUS_MAP = {
    active:    { cls: 'badge-green',  label: 'active' },
    running:   { cls: 'badge-green',  label: 'running' },
    working:   { cls: 'badge-green',  label: 'working' },
    done:      { cls: 'badge-blue',   label: 'done' },
    completed: { cls: 'badge-blue',   label: 'done' },
    success:   { cls: 'badge-blue',   label: 'done' },
    queued:    { cls: 'badge-yellow', label: 'queued' },
    pending:   { cls: 'badge-yellow', label: 'pending' },
    dispatched:{ cls: 'badge-yellow', label: 'pending' },
    spawning:  { cls: 'badge-yellow', label: 'pending' },
    booting:   { cls: 'badge-yellow', label: 'pending' },
    error:     { cls: 'badge-red',    label: 'error' },
    failed:    { cls: 'badge-red',    label: 'failed' },
    timeout:   { cls: 'badge-red',    label: 'failed' },
    dead:      { cls: 'badge-red',    label: 'failed' },
    idle:      { cls: 'badge-grey',   label: 'idle' },
  };

  function getStatus(st) {
    const s = (st || 'idle').toLowerCase();
    return STATUS_MAP[s] || { cls: 'badge-grey', label: s };
  }

  function renderTreeNode(node, prefix, isLast, lines) {
    if (!node) return;
    const role = (node.role || '').toUpperCase();
    const icon = ROLE_ICONS[role] || '•';
    const st = getStatus(node.status);
    const branch = prefix + (isLast ? '└── ' : '├── ');
    const nextPrefix = prefix + (isLast ? '    ' : '│   ');

    let html = '<div class="tree-line">';
    html += '<span class="branch">' + branch + '</span>';
    html += '<div class="tree-content">';
    html += '<span class="role-icon">' + icon + '</span>';
    html += '<span class="role-name">' + (node.role || '') + '</span>';
    html += '<span class="status-badge ' + st.cls + '">' + st.label + '</span>';
    if (node.model) {
      html += '<span class="model-badge">' + escapeHtml(node.model.split('/').pop()) + '</span>';
    }
    if (node.task) {
      html += '<span class="task-text">— ' + escapeHtml(node.task) + '</span>';
    }
    html += '</div></div>';
    lines.push(html);

    const kids = node.children || [];
    for (let i = 0; i < kids.length; i++) {
      renderTreeNode(kids[i], nextPrefix, i === kids.length - 1, lines);
    }
  }

  function escapeHtml(t) {
    if (!t) return '';
    return String(t).replace(/[&<>"']/g, function(m) {
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'})[m];
    });
  }

  function renderSandboxCard(item) {
    const tree = item.tree;
    const st = getStatus(item.status);
    const role = (tree.role || '').toUpperCase();
    const icon = ROLE_ICONS[role] || '⚡';

    let header = '<div class="card-header">';
    header += '<div class="card-title">' + icon + ' ' + escapeHtml(item.sandbox) + '</div>';
    header += '<div class="card-meta">';
    header += '<span class="badge ' + st.cls + '">' + st.label + '</span>';
    if (item.model) {
      header += '<span class="model-badge">' + escapeHtml(item.model) + '</span>';
    }
    header += '</div></div>';

    let body = '<div class="card-body"><div class="tree">';
    const lines = [];
    // Root node without branch prefix
    body += '<div class="tree-line">';
    body += '<span class="branch"></span>';
    body += '<div class="tree-content">';
    body += '<span class="role-icon">' + icon + '</span>';
    body += '<span class="role-name">' + (tree.role || '') + '</span>';
    body += '<span class="status-badge ' + st.cls + '">' + st.label + '</span>';
    if (tree.model) {
      body += '<span class="model-badge">' + escapeHtml(tree.model.split('/').pop()) + '</span>';
    }
    if (tree.task) {
      body += '<span class="task-text">— ' + escapeHtml(tree.task) + '</span>';
    }
    body += '</div></div>';

    const kids = tree.children || [];
    for (let i = 0; i < kids.length; i++) {
      renderTreeNode(kids[i], '', i === kids.length - 1, lines);
    }
    body += lines.join('');
    body += '</div></div>';

    const card = document.createElement('div');
    card.className = 'sandbox-card';
    card.innerHTML = header + body;
    card.onclick = function() { openSandbox(item.sandbox); };
    return card;
  }

  function updateStats(trees, summary) {
    let totalTokens = 0, totalBudget = 0, totalTools = 0, active = 0;
    for (const t of trees) {
      totalTokens += t.tokens_used || 0;
      totalBudget += t.tokens_budget || 0;
      totalTools += t.tool_calls || 0;
      const s = (t.status || '').toLowerCase();
      if (s === 'active' || s === 'running' || s === 'working') active++;
    }
    document.getElementById('stat-tokens').textContent = totalTokens.toLocaleString();
    document.getElementById('stat-tokens-sub').textContent = totalBudget > 0 ? ('of ' + totalBudget.toLocaleString()) : '';
    document.getElementById('stat-sandboxes').textContent = active.toString();
    document.getElementById('stat-sandboxes-sub').textContent = (trees.length) + ' total';
    document.getElementById('stat-tools').textContent = totalTools.toLocaleString();
    document.getElementById('stat-tools-sub').textContent = 'calls';
  }

  function renderTrees(data) {
    const container = document.getElementById('trees');
    const empty = document.getElementById('empty');
    const trees = data.trees || [];
    updateStats(trees, data);
    if (trees.length === 0) {
      container.innerHTML = '';
      empty.style.display = '';
      return;
    }
    empty.style.display = 'none';
    container.innerHTML = '';
    for (const t of trees) {
      container.appendChild(renderSandboxCard(t));
    }
  }

  let lastTrees = [];
  function treesEqual(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  async function loadTrees() {
    try {
      const res = await fetch('/api/v1/tree');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!treesEqual(data.trees, lastTrees)) {
        lastTrees = JSON.parse(JSON.stringify(data.trees || []));
        renderTrees(data);
      }
    } catch (e) {
      console.error('loadTrees error:', e);
    }
  }

  // SSE auto-refresh
  function connectSSE() {
    const es = new EventSource('/api/v1/events');
    es.addEventListener('summary', function() {
      loadTrees();
    });
    es.addEventListener('tree_update', function() {
      loadTrees();
    });
    es.addEventListener('error', function() {
      console.warn('SSE error');
    });
    es.onerror = function() {
      // Will auto-reconnect
    };
  }

  // Modal
  window.openSandbox = function(name) {
    const modal = document.getElementById('modal');
    const body = document.getElementById('modal-body');
    const title = document.getElementById('modal-title');
    const iconEl = document.getElementById('modal-icon');
    title.textContent = name;
    iconEl.textContent = '⚡';
    body.innerHTML = '<div class="loading">Loading...</div>';
    modal.classList.add('show');
    fetch('/api/v1/sandbox/' + encodeURIComponent(name))
      .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function(data) {
        body.innerHTML = '<pre>' + escapeHtml(JSON.stringify(data, null, 2)) + '</pre>';
      })
      .catch(function(err) {
        body.innerHTML = '<div class="error">Error: ' + escapeHtml(err.message) + '</div>';
      });
  };

  window.closeModal = function(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('modal').classList.remove('show');
  };

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') window.closeModal();
  });

  // Init
  loadTrees();
  connectSSE();
})();
</script>
</body>
</html>"""
