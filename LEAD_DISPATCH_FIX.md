# LEAD DISPATCH FIX — Plan to Make Dispatch Entries Actually Execute

## 1. What's Broken

### Root Cause
The dispatch queue is a **write-only system**. When `hero spawn` (or `hero go`) calls `enqueue()`, it writes a `.toon` file to `~/.hero/dispatch/` with `status: "pending"` — but **nothing ever reads that file and executes the task**.

### Specific Code Paths

| Step | What Happens | What Should Happen |
|------|-------------|-------------------|
| `hero spawn --sandbox X --task "..."` | Calls `SoldierSpawner.launch()` → `_launch_via_queue()` → `enqueue()` | ✅ Works |
| `enqueue()` writes `~/.hero/dispatch/<task_id>.toon` | File created with `status: "pending"` | ✅ Works |
| **The gap** | No consumer picks up "pending" tasks | ❌ Should execute via `sessions_spawn` or `subprocess` |
| `PipelineWatcher._tick()` | Only handles `status == "dispatched"` or `"completed"` | Ignores "pending" entries entirely |
| `PipelineExecutor._poll_tasks()` | Only polls already-dispatched tasks | Doesn't initiate execution |
| Sandbox state cache | Never updated to "active"/"running" | Should be updated when execution starts |

### Why It Exists
The architecture was designed for a **two-phase model**:
1. `hero go` queues tasks + outputs `sessions_spawn` commands for a "Communicator" (user or separate agent) to execute
2. The Communicator manually runs those commands

But `hero spawn` bypasses this — it expects immediate execution, not a manual handoff.

## 2. The Minimal Fix

### Option A: Dispatch Worker (Recommended)
Add a background worker that polls `~/.hero/dispatch/` and executes pending tasks automatically.

**New file:** `src/hero/dispatch/worker.py`

```python
"""Dispatch Worker — polls pending tasks and executes them.

Runs as a background thread (started by `hero watch` or standalone).
Reads pending dispatch files, executes via sessions_spawn or subprocess,
and updates status as the soldier progresses.
"""
```

**Core flow:**
```
Worker loop (every 3s):
  1. list_pending() → get all status="pending" tasks
  2. For each pending task:
     a. mark_dispatched(task_id)  # status: "pending" → "dispatched"
     b. Update sandbox state → "running" via SandboxState.update_status()
     c. Execute via sessions_spawn() or subprocess.Popen()
     d. Monitor execution, update dispatch status on completion
```

### Option B: Fix `SoldierSpawner` Directly
Make `_launch_via_queue()` actually call `sessions_spawn` instead of just writing a file.

**Pros:** Smaller change, immediate execution
**Cons:** Blocks the CLI until the soldier completes (bad for long tasks)

### Option C: Hybrid — Immediate for `spawn`, Deferred for `go`
- `hero spawn` → execute immediately via subprocess (legacy path always, or sessions_spawn inline)
- `hero go` → keep current behavior (queue + Communicator handoff)

**Verdict:** Option A is cleanest. The worker pattern scales to `hero go` too.

## 3. Syncing Sandbox State

### Current State Source
Sandbox status is read from `HEARTBEAT.toon` via `SandboxState.load()` → `heartbeat_data.get("status", "idle")`.

### When to Update
1. **On dispatch pickup:** `SandboxState(sandbox).update_status("running")`
2. **On completion:** `SandboxState(sandbox).update_status("idle")` (or "completed" briefly)
3. **On failure:** `SandboxState(sandbox).update_status("error")`

### Cache Invalidation
After each status update, call `invalidate_cache(sandbox)` so the viewport reads fresh data.

### Viewport Integration
The `MetricsCollector.collect()` already reads from `StateCache` and dispatch files. Once the worker updates both:
- `HEARTBEAT.toon` → status field reflects actual state
- Dispatch file → `status: "running"` with `tool_calls` incrementing
- Viewport shows live agents in the tree hierarchy

## 4. File Changes Needed

### New Files
| File | Purpose |
|------|---------|
| `src/hero/dispatch/worker.py` | Background worker that executes pending dispatches |
| `src/hero/commands/worker.py` | CLI command: `hero worker start/stop/status` |

### Modified Files
| File | Change |
|------|--------|
| `src/hero/soldier/spawner.py` | In `_launch_via_queue()`: after `enqueue()`, optionally trigger immediate execution or rely on worker |
| `src/hero/commands/spawn.py` | After `spawner.launch()`, update sandbox status to "running" |
| `src/hero/pipeline/watcher.py` | Start the dispatch worker alongside the pipeline watcher (or merge them) |
| `src/hero/commands/watch.py` | Also start dispatch worker when `hero watch` runs |
| `src/hero/dispatch/dispatch.py` | Add `get_pending_tasks()` helper (already exists as `list_pending()`) |
| `src/hero/state/sandbox.py` | No changes needed — `update_status()` already exists |

### Key Implementation Details

#### `src/hero/dispatch/worker.py` (new)
```python
class DispatchWorker:
    """Polls pending dispatch files and executes them."""
    
    def __init__(self, poll_interval: int = 3):
        self.poll_interval = poll_interval
        self._running = False
        self._active_sessions: dict[str, Any] = {}  # task_id → session handle
    
    def tick(self):
        """One scan cycle."""
        from hero.soldier.dispatch import list_pending, mark_dispatched
        from hero.state.sandbox import SandboxState, invalidate_cache
        
        for task in list_pending():
            task_id = task["task_id"]
            sandbox = task["sandbox"]
            
            # Mark as dispatched
            mark_dispatched(task_id)
            
            # Update sandbox state
            ss = SandboxState(sandbox)
            ss.update_status("running")
            invalidate_cache(sandbox)
            
            # Execute
            self._execute_task(task)
    
    def _execute_task(self, task: dict):
        """Execute a dispatch task via sessions_spawn or subprocess."""
        from hero.soldier.dispatch import get_sessions_spawn_command
        
        # Build sessions_spawn params
        spawn_params = get_sessions_spawn_command(task)
        
        # Execute via OpenClaw sessions_spawn (if available)
        # or fallback to hermes-agent subprocess
        ...
```

#### Modification to `src/hero/commands/spawn.py`
After the `spawner.launch()` call, add sandbox state update:
```python
# After spawner.launch() succeeds:
from hero.state.sandbox import SandboxState, invalidate_cache
ss = SandboxState(sandbox)
ss.update_status("running")
invalidate_cache(sandbox)
```

#### Modification to `src/hero/pipeline/watcher.py`
In `PipelineWatcher.__init__()` or `_tick()`, also run dispatch worker logic:
```python
# In _tick(), before checking dispatched tasks:
from hero.dispatch.worker import DispatchWorker
self._worker.tick()  # picks up pending dispatches
```

Or start it as a separate thread in `hero watch`.

## 5. Risk Assessment

### Low Risk
| Risk | Mitigation |
|------|-----------|
| Worker crashes mid-execution | Dispatch file stays "dispatched" — watcher already handles stale detection |
| Double execution | `mark_dispatched()` is atomic (file write) — worker checks status before executing |
| Sandbox state corruption | `update_status()` only writes to HEARTBEAT.toon — isolated file |

### Medium Risk
| Risk | Mitigation |
|------|-----------|
| sessions_spawn fails | Fallback to subprocess (legacy path) — already has circuit breaker |
| Too many concurrent soldiers | Worker should limit concurrency (configurable, default 3) |
| Watcher + worker race condition | Merge into single `PipelineWatcher` or use file locks |

### High Risk (if not handled)
| Risk | Mitigation |
|------|-----------|
| Worker never started | `hero spawn` silently writes dispatch file but nothing executes — **same as current bug** |
| **Fix:** | Ensure `hero watch` starts worker, OR make `hero spawn` execute inline when worker isn't running |

### Recommended Approach
1. **Immediate fix:** Modify `SoldierSpawner._launch_via_queue()` to execute inline (subprocess) when worker isn't detected
2. **Proper fix:** Add `DispatchWorker` and start it via `hero watch`
3. **Long-term:** Merge worker into `PipelineWatcher` for single-daemon architecture

## 6. Implementation Order

1. **Quick win (30 min):** Add sandbox state update to `spawn.py` after launch — at least the viewport shows "running" even if execution is deferred
2. **Core fix (2 hrs):** Implement `DispatchWorker` in `src/hero/dispatch/worker.py`
3. **Integration (1 hr):** Wire worker into `hero watch` and `PipelineWatcher`
4. **Testing (1 hr):** Verify dispatch → execution → completion → state sync cycle
5. **Cleanup (30 min):** Remove dead code paths, update docs

---

**Bottom line:** The dispatch queue is a pipe with no consumer. The fix is to add one — either inline in the spawner or as a background worker. The state sync is already architected; it just needs to be called.
