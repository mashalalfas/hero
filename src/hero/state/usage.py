"""Usage tracker — records actual token consumption from subagent completions."""
import json
import time
from pathlib import Path

USAGE_DIR = Path.home() / ".hero" / "usage"
USAGE_DIR.mkdir(parents=True, exist_ok=True)


def record_usage(task_id: str, sandbox: str, tokens_used: int, model: str, elapsed_seconds: int):
    """Write actual usage for a completed subagent."""
    record = {
        "task_id": task_id,
        "sandbox": sandbox,
        "tokens_used": tokens_used,
        "model": model,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": time.time()
    }
    (USAGE_DIR / f"{task_id}.json").write_text(json.dumps(record))


def get_usage(task_id: str) -> dict | None:
    """Get recorded usage for a task."""
    f = USAGE_DIR / f"{task_id}.json"
    if f.exists():
        return json.loads(f.read_text())
    return None


def sum_sandbox_usage(sandbox: str) -> int:
    """Sum all usage records for a sandbox."""
    total = 0
    for f in USAGE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("sandbox") == sandbox:
                total += data.get("tokens_used", 0)
        except (json.JSONDecodeError, OSError):
            pass
    return total
