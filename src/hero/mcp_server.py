"""HERO MCP Server — exposes HERO CLI commands as MCP tools for opencode.

Runs over stdio using the Model Context Protocol (JSON-RPC 2.0).
Callable tools map 1:1 to HERO CLI commands.

Usage:
    python -m hero.mcp_server
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path


# ── MCP Protocol Helpers ──────────────────────────────────────────────────────

JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "hero-mcp"
SERVER_VERSION = "0.1.0"

HERO_PROJECT = Path(__file__).parent.parent.parent
RUNNER = ["uv", "run", "--project", str(HERO_PROJECT), "python", "-m", "hero"]


def jsonrpc_error(id: int | str | None, code: int, message: str, data: object = None) -> dict:
    msg: dict = {"jsonrpc": JSONRPC_VERSION, "error": {"code": code, "message": message}}
    if id is not None:
        msg["id"] = id
    if data is not None:
        msg["error"]["data"] = data
    return msg


def jsonrpc_result(id: int | str, result: object) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "result": result}


def jsonrpc_notification(method: str, params: object = None) -> dict:
    msg: dict = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# ── Tool Definitions ──────────────────────────────────────────────────────────

def run_hero(args: list[str]) -> str:
    """Run a HERO CLI command and return its output."""
    cmd = RUNNER + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(HERO_PROJECT),
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
        raise RuntimeError(error_msg)
    return result.stdout.strip()


TOOLS = [
    {
        "name": "hero_scan",
        "description": "Discover projects in ~/Development/ and create sandbox entries in INDEX.toon",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hero_status",
        "description": "Show all sandbox states in compact TOON format",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hero_spawn",
        "description": "Launch a soldier agent in a sandbox with TOON context injection",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
                "task": {"type": "string", "description": "Task description"},
                "budget": {"type": "integer", "description": "Token budget (optional)"},
            },
            "required": ["sandbox", "task"],
        },
    },
    {
        "name": "hero_go",
        "description": "One-command full pipeline: plan → dispatch → spawn → verify → archive → report",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
                "task": {"type": "string", "description": "Task description"},
            },
            "required": ["sandbox", "task"],
        },
    },
    {
        "name": "hero_budget_summary",
        "description": "Table of all sandbox budgets with color-coded utilization",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hero_budget_alert",
        "description": "List sandboxes with remaining tokens below threshold",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "integer", "description": "Token threshold (default 2000)"},
            },
        },
    },
    {
        "name": "hero_check",
        "description": "6-point health diagnostic for a sandbox (budget, heartbeat, git, build, circuit, dispatch)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
            },
            "required": ["sandbox"],
        },
    },
    {
        "name": "hero_dispatch_list",
        "description": "Show all dispatched tasks in the queue",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hero_dlq_list",
        "description": "List failed tasks in the dead letter queue",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hero_deploy",
        "description": "Deploy soldier agents to multiple sandboxes simultaneously",
        "inputSchema": {
            "type": "object",
            "properties": {
                "targets": {"type": "string", "description": "Comma-separated sandbox names"},
                "task": {"type": "string", "description": "Task description"},
            },
            "required": ["targets", "task"],
        },
    },
    {
        "name": "hero_orchestrate",
        "description": "Lead agent orchestrates army execution for a sandbox",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
                "goal": {"type": "string", "description": "High-level goal to decompose"},
            },
            "required": ["sandbox", "goal"],
        },
    },
    {
        "name": "hero_assemble",
        "description": "Full army pipeline: orchestrate → dispatch → spawn-ready JSON",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
                "goal": {"type": "string", "description": "High-level goal"},
            },
            "required": ["sandbox", "goal"],
        },
    },
    {
        "name": "hero_budget_history",
        "description": "Show recent budget events for a sandbox",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandbox": {"type": "string", "description": "Sandbox/project name"},
            },
            "required": ["sandbox"],
        },
    },
]


# ── Request Handlers ──────────────────────────────────────────────────────────

TOOL_MAP = {
    "hero_scan": lambda args: run_hero(["scan"]),
    "hero_status": lambda args: run_hero(["status"]),
    "hero_spawn": lambda args: run_hero(
        ["spawn", "--sandbox", args["sandbox"], "--task", args["task"]]
        + (["--budget", str(args["budget"])] if "budget" in args else [])
    ),
    "hero_go": lambda args: run_hero(
        ["go", "--sandbox", args["sandbox"], "--task", args["task"]]
    ),
    "hero_budget_summary": lambda args: run_hero(["budget", "summary"]),
    "hero_budget_alert": lambda args: run_hero(
        ["budget", "alert", "--threshold", str(args.get("threshold", 2000))]
    ),
    "hero_check": lambda args: run_hero(["check", "--sandbox", args["sandbox"]]),
    "hero_dispatch_list": lambda args: run_hero(["dispatch", "list"]),
    "hero_dlq_list": lambda args: run_hero(["dlq", "list"]),
    "hero_deploy": lambda args: run_hero(
        ["deploy", "--targets", args["targets"], "--task", args["task"]]
    ),
    "hero_orchestrate": lambda args: run_hero(
        ["orchestrate", "--sandbox", args["sandbox"], "--goal", args["goal"]]
    ),
    "hero_assemble": lambda args: run_hero(
        ["assemble", "--sandbox", args["sandbox"], "--goal", args["goal"]]
    ),
    "hero_budget_history": lambda args: run_hero(
        ["budget", "history", "--sandbox", args["sandbox"]]
    ),
}


def handle_request(request: dict) -> dict | None:
    """Process a single JSON-RPC request and return a response, or None for notifications."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {}) or {}

    if method == "initialize":
        return jsonrpc_result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "notifications/initialized":
        return None

    if method == "notifications/cancelled":
        return None

    if method == "shutdown":
        return jsonrpc_result(req_id, None)

    if method == "tools/list":
        return jsonrpc_result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOL_MAP.get(tool_name)
        if handler is None:
            return jsonrpc_error(req_id, -32601, f"Tool not found: {tool_name}")
        try:
            result_text = handler(tool_args)
            return jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": result_text}],
            })
        except RuntimeError as e:
            return jsonrpc_error(req_id, -32000, str(e), {"tool": tool_name})
        except subprocess.TimeoutExpired:
            return jsonrpc_error(req_id, -32000, f"Tool '{tool_name}' timed out (120s)")
        except KeyError as e:
            return jsonrpc_error(req_id, -32602, f"Missing required argument: {e}")
        except Exception as e:
            return jsonrpc_error(req_id, -32000, f"Tool '{tool_name}' error: {e}")

    return jsonrpc_error(req_id, -32601, f"Method not found: {method}")


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    """Read JSON-RPC messages from stdin, process, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            # Can't respond without an ID — write error anyway
            sys.stderr.write(f"HERO MCP: invalid JSON: {e}\n")
            sys.stderr.flush()
            continue

        try:
            response = handle_request(request)
        except Exception as e:
            req_id = request.get("id") if isinstance(request, dict) else None
            response = jsonrpc_error(req_id, -32603, f"Internal error: {e}")

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
