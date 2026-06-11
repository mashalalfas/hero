# SOLDIER BRIEF 4 — Control Features (Kill Endpoint + UI)

## TASK
Add sandbox kill/control API endpoint to server.py and wire the confirmation flow in the frontend.

## FILES TO MODIFY
- `/home/max/Development/HERO/src/hero/web/server.py` — Add kill endpoint

## FILES TO CREATE (or verify exist from Soldier 3)
- `/home/max/Development/HERO/src/hero/web/static/js/components/controls.js` — Kill button UI
- `/home/max/Development/HERO/src/hero/web/static/js/components/modal.js` — Confirmation modal

## SPEC

### Server: Kill Endpoint

Add to `server.py` after existing routes:

```python
@app.post("/api/v1/sandbox/{name}/kill")
async def api_kill_sandbox(name: str, request: Request) -> JSONResponse:
    """Kill a sandbox. Requires Bearer auth + confirmation token in body."""
    _check_auth(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON body required")

    confirmation_token = body.get("confirmation_token")
    if not confirmation_token:
        raise HTTPException(status_code=400, detail="confirmation_token required")

    # Confirmation token must be the sandbox name (simple proof-of-intent)
    if confirmation_token != name:
        raise HTTPException(status_code=400, detail="confirmation_token must match sandbox name")

    # Verify sandbox exists
    try:
        detail = collect_sandbox_detail(name)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Sandbox '{name}' not found")
    except HTTPException:
        raise
    except Exception:
        pass  # Sandbox might still be killable even if detail fetch fails

    # Execute kill via hero CLI
    import subprocess
    try:
        result = subprocess.run(
            ["hero", "kill", name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Kill command failed"
            logger.warning(f"hero kill {name} failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="hero CLI not found in PATH")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Kill command timed out")

    logger.info(f"Sandbox '{name}' killed successfully")
    return JSONResponse({
        "status": "killed",
        "sandbox": name,
        "message": f"Sandbox '{name}' has been terminated"
    })
```

### Server: Spawn Endpoint (bonus)

```python
@app.post("/api/v1/sandbox/{name}/spawn")
async def api_spawn_sandbox(name: str, request: Request) -> JSONResponse:
    """Spawn a new sandbox. Requires Bearer auth."""
    _check_auth(request)

    try:
        body = await request.json()
    except Exception:
        body = {}

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

    return JSONResponse({
        "status": "spawned",
        "sandbox": name,
        "message": f"Sandbox '{name}' spawn initiated"
    })
```

### Frontend: controls.js

```javascript
// Import: api.js killSandbox, modal.js showModal, toast.js showToast
// Import: state.js getState, subscribe

// renderControls(container, sandboxName):
//   - Only render if sandbox is active/running/error
//   - Kill button: red, ghost style, skull icon
//   - On click: showModal with warning message
//     - Title: "Kill Sandbox?"
//     - Message: "This will terminate {name} and all running tasks."
//     - Confirm text: "Kill {name}" (red button)
//     - On confirm: call killSandbox(name, name) → showToast success/error
//   - Button has data-sandbox attribute for event delegation
```

### Frontend: modal.js

```javascript
// showModal({ title, message, confirmText, onConfirm, onCancel }):
//   - Create overlay div with glass background
//   - Modal panel centered, max-width 480px
//   - Title in font-display
//   - Message text
//   - Cancel button (ghost) + Confirm button (danger)
//   - Focus confirm button on open
//   - Enter key triggers confirm
//   - Escape key triggers cancel
//   - Focus trap: Tab cycles between cancel and confirm
//   - Remove modal from DOM on close

// closeModal():
//   - Remove overlay with fade-out animation
```

## DESIGN
- Kill button: `var(--color-danger)` border/text, transparent bg, hover fills red
- Modal: `var(--glass-bg)` with `backdrop-filter: blur(var(--glass-blur-heavy))`
- Confirm button: solid `var(--color-danger)` bg, white text
- Warning icon: ⚠️ in modal header
- Animation: modal fades in with scale(0.95) → scale(1)

## CONSTRAINTS
- **Auth required:** All control endpoints check Bearer token via `_check_auth(request)`
- **Confirmation required:** Kill endpoint requires `confirmation_token` matching sandbox name
- **No destructive ops without UI confirmation:** Frontend must show modal before calling kill
- **Error handling:** Server returns structured JSON errors, frontend shows toast
- **Subprocess timeout:** 30s for kill, 60s for spawn
- **Logging:** All control actions logged via `logger.info/warning`

## ACCEPTANCE
1. `POST /api/v1/sandbox/{name}/kill` endpoint exists in server.py
2. Endpoint requires Bearer auth (401 without valid token)
3. Endpoint requires `confirmation_token` in body (400 without)
4. Endpoint runs `hero kill <name>` and returns result
5. controls.js renders kill button only for active/running sandboxes
6. Click kill → modal appears → confirm → API call → toast feedback
7. Modal handles Enter/Escape keyboard events
8. All errors shown via toast, not alert()
9. No hardcoded auth — uses auth.js getAuthHeaders()
