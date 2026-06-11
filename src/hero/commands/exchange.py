"""hero exchange — Inter-agent message bus commands."""

from __future__ import annotations

import click

from hero.exchange.core import ExchangeLayer
from hero.exchange.task_list import TaskList, Assignment
from hero.exchange.pipe import ResultPipe
from hero.exchange.review import Review
from hero.exchange.message import MailMessage, iter_messages, STATUS_READ, STATUS_EXPIRED, STATUS_FAILED
from hero.exchange.reliability import purge_old
from hero.logging import get_logger

logger = get_logger("commands.exchange")


@click.group()
def exchange():
    """Inter-agent message bus — communicate between soldiers."""
    pass


@exchange.command()
@click.argument("target")
@click.argument("message")
@click.option("--type", "msg_type", default="direct",
              type=click.Choice(["direct", "review", "pipe"]))
@click.option("--priority", default="normal",
              type=click.Choice(["low", "normal", "high", "critical"]))
@click.option("--ttl", default=3600, type=int, help="Message TTL in seconds")
@click.option("--reply-to", default=None, help="Reply to a specific message ID")
def send(target: str, message: str, msg_type: str, priority: str,
         ttl: int, reply_to: str | None):
    """Send a message to a target sandbox.

    TARGET: sandbox name (e.g. "freya") or "sandbox:role" (e.g. "sook-pro:architect")
    """
    parts = target.split(":")
    to_sandbox = parts[0]
    to_role = parts[1] if len(parts) > 1 else "soldier"

    xl = ExchangeLayer()
    msg_id = xl.send(
        to_sandbox=to_sandbox,
        to_role=to_role,
        body=message,
        msg_type=msg_type,
        priority=priority,
        ttl_seconds=ttl,
        reply_to=reply_to,
    )
    click.echo(f"  Sent: {msg_id}")


@exchange.command()
@click.argument("message")
@click.option("--role", default=None, help="Filter: only send to this role")
@click.option("--sandbox", default=None, help="Filter: only send to this sandbox")
@click.option("--priority", default="normal",
              type=click.Choice(["low", "normal", "high", "critical"]))
def broadcast(message: str, role: str | None, sandbox: str | None, priority: str):
    """Broadcast a message to all active soldiers."""
    xl = ExchangeLayer()
    msg_id = xl.broadcast(
        body=message,
        role_filter=role,
        sandbox_filter=sandbox,
        priority=priority,
    )
    click.echo(f"  Broadcast sent: {msg_id}")


@exchange.command()
@click.option("--all", "show_all", is_flag=True, help="Show delivered/read too")
@click.option("--from", "from_sandbox", default=None, help="Filter by sender sandbox")
@click.option("--type", "msg_type", default=None, help="Filter by message type")
@click.option("--watch", is_flag=True, help="Continuous polling")
@click.option("--interval", default=5, type=int, help="Poll interval in watch mode")
@click.option("--max", "max_results", default=5, type=int, help="Max messages to return")
def listen(show_all: bool, from_sandbox: str | None, msg_type: str | None,
           watch: bool, interval: int, max_results: int):
    """Listen for incoming messages (max 5 by default — Guardrail)."""
    xl = ExchangeLayer()

    if watch:
        import time
        try:
            while True:
                _print_inbox(xl, show_all, from_sandbox, msg_type, max_results)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    else:
        _print_inbox(xl, show_all, from_sandbox, msg_type, max_results)


def _print_inbox(xl: ExchangeLayer, show_all: bool, from_filter: str | None,
                 msg_type: str | None, max_results: int = 5):
    messages = xl.listen(
        include_delivered=show_all,
        msg_type=msg_type,
        max_results=max_results,
    )

    if not messages:
        click.echo("  No new messages.")
        return

    for msg in messages:
        if from_filter and msg.from_sandbox != from_filter:
            continue
        click.echo(f"  [{msg.msg_id[:8]}] {msg.from_sandbox}:{msg.from_role} → {msg.to_sandbox}:{msg.to_role}")
        click.echo(f"      Type: {msg.msg_type} | Priority: {msg.priority} | Status: {msg.status}")
        body_lines = msg.body.split("\n")[:2]
        for bl in body_lines:
            click.echo(f"      {bl}")
        click.echo()


@exchange.command()
@click.argument("msg_id")
def mark_read(msg_id: str):
    """Acknowledge a message as read (archives it)."""
    xl = ExchangeLayer()
    if xl.mark_read(msg_id):
        click.echo(f"  Message {msg_id[:12]} marked as read (archived).")
    else:
        click.echo(f"  Message {msg_id[:12]} not found.")


@exchange.command()
@click.argument("msg_id")
@click.argument("message")
def reply(msg_id: str, message: str):
    """Reply to a message (shortcut for send --reply-to)."""
    xl = ExchangeLayer()
    original = xl.get_message(msg_id)
    if not original:
        click.echo(f"  Message {msg_id[:12]} not found.")
        return
    new_id = xl.send(
        to_sandbox=original.from_sandbox,
        to_role=original.from_role,
        body=message,
        reply_to=msg_id,
    )
    click.echo(f"  Replied: {new_id}")


@exchange.command()
def status():
    """Show exchange queue health."""
    xl = ExchangeLayer()

    pending = 0
    delivered = 0
    read_count = 0
    failed = 0
    expired = 0
    by_type: dict[str, int] = {}

    for path in iter_messages():
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status == "pending":
            pending += 1
        elif msg.status == "delivered":
            delivered += 1
        elif msg.status == "read":
            read_count += 1
        elif msg.status == "failed":
            failed += 1
        elif msg.status == "expired":
            expired += 1
        by_type[msg.msg_type] = by_type.get(msg.msg_type, 0) + 1

    roster = xl.get_roster()

    click.echo("  Exchange Layer Status")
    click.echo(f"  ─────────────────────")
    click.echo(f"  Messages:")
    click.echo(f"    Pending:   {pending}")
    click.echo(f"    Delivered: {delivered}")
    click.echo(f"    Read:      {read_count}")
    click.echo(f"    Failed:    {failed}")
    click.echo(f"    Expired:   {expired}")
    click.echo(f"  By type:")
    for t, c in sorted(by_type.items()):
        click.echo(f"    {t}: {c}")
    click.echo(f"  ─────────────────────")
    click.echo(f"  Active roster: {len(roster)} soldier(s)")
    for r in roster:
        click.echo(f"    {r.get('sandbox', '?')} — {r.get('role', '?')} ({r.get('soldier_id', '?')[:8]})")
    click.echo(f"  ─────────────────────")


@exchange.command()
def roster():
    """Show active soldier roster."""
    xl = ExchangeLayer()
    roster_data = xl.get_roster()
    if not roster_data:
        click.echo("  No active soldiers.")
        return
    click.echo(f"  Active soldiers: {len(roster_data)}")
    for r in roster_data:
        click.echo(f"    {r.get('sandbox', '?')} — {r.get('role', '?')} — {r.get('model', '?')}")
        click.echo(f"      spawned: {r.get('spawned_at', '?')}")


@exchange.command()
@click.option("--type", "msg_type", default=None, help="Purge only this message type")
@click.option("--older-than", default=60, type=int, help="Age threshold in minutes")
def purge(msg_type: str | None, older_than: int):
    """Remove old delivered/read/expired messages."""
    import time

    now = time.time()
    cutoff = now - (older_than * 60)
    terminal = {"read", "expired", "failed"}

    removed = 0
    for path in iter_messages(msg_type):
        msg = MailMessage.from_toon(path)
        if not msg:
            continue
        if msg.status in terminal:
            try:
                mtime = path.stat().st_mtime
                if mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                pass

    click.echo(f"  Purged {removed} message(s).")


# ── Task list subcommands ─────────────────────────────────────

@exchange.group()
def task():
    """Shared task list operations."""
    pass


@task.command("post")
@click.argument("title")
@click.argument("description")
@click.option("--files", default=None, help="Comma-separated file list")
@click.option("--depends-on", default=None, help="Comma-separated task IDs")
@click.option("--ttl", default=7200, type=int, help="Task TTL in seconds")
def task_post(title: str, description: str, files: str | None,
              depends_on: str | None, ttl: int):
    """Post a task to the shared task list."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    files_list = [f.strip() for f in files.split(",")] if files else None
    depends_list = [d.strip() for d in depends_on.split(",")] if depends_on else None
    task_id = tl.post(title, description, files=files_list, depends_on=depends_list, ttl_seconds=ttl)
    click.echo(f"  Task posted: {task_id}")


@task.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks including claimed/completed")
def task_list_cmd(show_all: bool):
    """List available tasks."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    tasks = tl.list_available()
    if not tasks:
        click.echo("  No available tasks.")
        return

    click.echo(f"  Available tasks: {len(tasks)}")
    for t in tasks:
        click.echo(f"    [{t['msg_id'][:8]}] {t['title']}")
        click.echo(f"      Status: {t['status']}")


@task.command("claim")
@click.argument("task_id")
def task_claim(task_id: str):
    """Claim a task from the shared list."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    result = tl.claim(task_id, claimant_sandbox="self", claimant_role="soldier")
    if result:
        click.echo(f"  Claimed: {result['title']}")
    else:
        click.echo(f"  Could not claim {task_id[:12]} — already claimed or not found.")


@task.command("done")
@click.argument("task_id")
@click.argument("result")
def task_done(task_id: str, result: str):
    """Mark a claimed task as completed."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    if tl.done(task_id, result, claimant_sandbox="self"):
        click.echo(f"  Task {task_id[:12]} marked as completed.")


@task.command("fail")
@click.argument("task_id")
@click.argument("reason")
def task_fail(task_id: str, reason: str):
    """Mark a claimed task as failed."""
    xl = ExchangeLayer()
    tl = TaskList(xl)
    if tl.fail(task_id, reason, claimant_sandbox="self"):
        click.echo(f"  Task {task_id[:12]} marked as failed.")


# ── Pipe subcommands ──────────────────────────────────────────

@exchange.group()
def pipe():
    """Pipeline result passing."""
    pass


@pipe.command("push")
@click.argument("target")
@click.argument("task_id")
@click.argument("result", default="")
def pipe_push(target: str, task_id: str, result: str):
    """Push result to next pipeline soldier."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    parts = target.split(":")
    to_sandbox = parts[0]
    to_target = parts[1] if len(parts) > 1 else "soldier"
    msg_id = rp.push(to_sandbox, to_target, task_id, result)
    click.echo(f"  Pipe result pushed: {msg_id}")


@pipe.command("pull")
def pipe_pull():
    """Get next pipe result for this soldier."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    msg = rp.pull(for_sandbox="self", for_role="soldier")
    if msg:
        click.echo(f"  [{msg.msg_id[:8]}] Pipeline result from {msg.from_sandbox}")
        click.echo(msg.body[:500])
    else:
        click.echo("  No pipe results waiting.")


@pipe.command("status")
@click.argument("task_id")
def pipe_status(task_id: str):
    """Show pipeline chain status for a task."""
    xl = ExchangeLayer()
    rp = ResultPipe(xl)
    status_info = rp.status(task_id)
    click.echo(f"  Pipeline for task {task_id[:12]}:")
    for pm in status_info["pipe_messages"]:
        click.echo(f"    [{pm['msg_id'][:8]}] → {pm['to']} ({pm['status']})")


# ── Review subcommands ────────────────────────────────────────

@exchange.group()
def review():
    """Adversarial review operations."""
    pass


@review.command("request")
@click.argument("target")
@click.argument("task_id")
@click.option("--timeout", default=600, type=int, help="Review timeout seconds")
def review_request(target: str, task_id: str, timeout: int):
    """Request independent review of a completed task."""
    xl = ExchangeLayer()
    rv = Review(xl)
    parts = target.split(":")
    target_sandbox = parts[0]
    rev_id = rv.request(
        target_sandbox=target_sandbox,
        task_id=task_id,
        timeout_seconds=timeout,
    )
    click.echo(f"  Review requested: {rev_id}")


@review.command("respond")
@click.argument("msg_id")
@click.argument("verdict", type=click.Choice(["pass", "flag", "fail"]))
@click.argument("notes", default="")
def review_respond(msg_id: str, verdict: str, notes: str):
    """Respond to a review request."""
    xl = ExchangeLayer()
    rv = Review(xl)
    resp_id = rv.respond(msg_id, verdict, notes=notes)
    if resp_id:
        click.echo(f"  Review response sent: {resp_id}")
    else:
        click.echo("  Could not respond — review request not found.")


@review.command("status")
@click.argument("task_id")
def review_status(task_id: str):
    """Show review status for a task."""
    xl = ExchangeLayer()
    rv = Review(xl)
    info = rv.status(task_id)
    click.echo(f"  Review for task {task_id[:12]}:")
    click.echo(f"    Requests:  {len(info['requests'])}")
    click.echo(f"    Responses: {len(info['responses'])}")
    click.echo(f"    Pending:   {info['pending']}")
    for req in info["requests"]:
        click.echo(f"    [{req['msg_id'][:8]}] by {req['from']} → {req['to']} ({req['status']})")
    for resp in info["responses"]:
        click.echo(f"    RESP [{resp['msg_id'][:8]}] {resp['verdict']}")


# ── Assignment subcommands ────────────────────────────────────

@exchange.group()
def assign():
    """Per-soldier assignment management (Guardrail 4)."""
    pass


@assign.command("write")
@click.argument("deploy_id")
@click.argument("soldier_id")
@click.argument("task_id")
@click.option("--role", default="soldier")
def assign_write(deploy_id: str, soldier_id: str, task_id: str, role: str):
    """Write an assignment file for a soldier."""
    Assignment.write_assignments(deploy_id, {
        soldier_id: {"my_task": task_id, "my_role": role},
    })
    click.echo(f"  Assignment written for {soldier_id}")


@assign.command("read")
@click.argument("deploy_id")
@click.argument("soldier_id")
def assign_read(deploy_id: str, soldier_id: str):
    """Read a soldier's assignment."""
    data = Assignment.read_assignment(deploy_id, soldier_id)
    if data:
        click.echo(f"  Assignment for {soldier_id}:")
        for k, v in data.items():
            click.echo(f"    {k}: {v}")
    else:
        click.echo(f"  No assignment found for {soldier_id}.")
