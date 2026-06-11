# Exchange Layer — Inter-Agent Message Bus

> **Spec Version:** 1.0.0  
> **Date:** 2026-06-07  
> **Status:** Draft  
> **Priority:** #1 (blocks Agent Skills & Dynamic Workflows)

---

## 1. Overview & Motivation

### Problem

HERO soldiers cannot communicate with each other. Each soldier is spawned in isolation, receives a task, works on it, reports back to the orchestrator, and exits. There is no mechanism for:

- One soldier to pass partial results to another
- A team lead to coordinate multiple soldiers via a shared task list
- A reviewer soldier to independently verify another soldier's work
- Multiple soldiers to collaborate on interdependent files without stepping on each other

### Solution

The **Exchange Layer** is a file-based inter-agent message bus. Soldiers write and read messages as `.toon` files in `~/.hero/exchange/`. The orchestrator (Lead) acts as the **Exchange Broker** — it creates channels, routes messages, and cleans up when soldiers complete.

### Design Principles

1. **File-based** — Consistent with HERO's TOON approach. No database, no network, no external dependencies.
2. **Async by default** — Soldiers check for messages when they're ready. No blocking reads.
3. **At-least-once delivery** — Messages persist until acknowledged. Dead letter for failures.
4. **No shared mutable state** — Messages are append-only. Soldiers own their output.
5. **Transparent to existing code** — `--exchange` flag enables it. Without the flag, behavior is identical to today.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LEAD (Orchestrator)                   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Exchange Broker                        │   │
│  │  - Creates channels per deploy                    │   │
│  │  - Writes task list (shared)                      │   │
│  │  - Routes messages between soldiers               │   │
│  │  - Monitors TTL / cleanup                         │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
            ~/.hero/exchange/<deploy_id>/
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
     ┌────────┐   ┌────────┐   ┌────────┐
     │Soldier │   │Soldier │   │Soldier │
     │  A     │◄──┤  B     ├──►│  C     │
     │(Design)│   │(Code)  │   │(Review)│
     └────────┘   └────────┘   └────────┘
          │             │             │
          ▼             ▼             ▼
     ┌─────────────────────────────────────┐
     │         Result Channel              │
     │  (Lead reads when all done)         │
     └─────────────────────────────────────┘
```

### Directory Structure

```
~/.hero/exchange/
  └── <deploy_id>/                    # One exchange per deploy
        ├── CHANNEL.toon              # Channel registry
        ├── TASKS.toon                # Shared task list (Agent Teams pattern)
        ├── messages/
        │   ├── msg_<uuid>.toon       # Individual messages
        │   └── ...
        ├── queues/
        │   ├── <soldier_id>_inbox/   # Per-soldier incoming message queue
        │   │   └── msg_<uuid>.toon
        │   ├── <soldier_id>_outbox/  # Per-soldier outgoing (for retry)
        │   └── ...
        └── status/
            └── <soldier_id>.toon     # Per-soldier heartbeat/status
```

---

## 3. Data Model

### Message Schema (TOON format)

```
# ~/.hero/exchange/<deploy_id>/messages/msg_<uuid>.toon

id: "<uuid>"
deploy_id: "<deploy_id>"
type: "direct|broadcast|task|result|review_request|review_response"
status: "pending|delivered|read|expired"
from: "<soldier_id|lead>"
to: "<soldier_id|*|task_list>"
thread_id: "<optional_thread_id>"
created_at: "<ISO-8601>"
delivered_at: "<ISO-8601|null>"
read_at: "<ISO-8601|null>"
ttl_seconds: 3600
body: |
  <message content — plain text or TOON-encoded structured data>
```

### Channel Registry (CHANNEL.toon)

```
# ~/.hero/exchange/<deploy_id>/CHANNEL.toon
# Declares all participants and their roles in this exchange

deploy_id: "<deploy_id>"
created_at: "<ISO-8601>"
status: "active|completed|failed"
lead_soldier_id: "<soldier_id>"
soldiers:
  - id: "<soldier_id_A>"
    role: "architect|developer|reviewer|tester"
    status: "pending|active|completed|failed"
    sandbox: "<sandbox_name>"
    inbox_polled: 0
    messages_sent: 0
    messages_received: 0
  - id: "<soldier_id_B>"
    role: "..."
    ...
```

### Shared Task List (TASKS.toon)

```
# ~/.hero/exchange/<deploy_id>/TASKS.toon
# Agent Teams pattern — lead writes tasks, soldiers claim them

tasks:
  - id: "task_001"
    description: "Implement login API endpoint"
    assigned_to: "<soldier_id|null>"
    status: "pending|claimed|in_progress|completed|failed|verified"
    depends_on[0]: "task_002"      # Optional dependency
    created_at: "<ISO-8601>"
    completed_at: "<ISO-8601|null>"
    result: "<path_to_output_file|null>"
  - id: "task_002"
    description: "Design auth schema"
    assigned_to: "<soldier_id>"
    status: "completed"
    ...
```

---

## 4. Communication Patterns

### Pattern 1: Direct Messaging (Soldier → Soldier)

```
Soldier A                          Exchange Layer                      Soldier B
    │                                    │                                │
    │  Send "design ready, review?"      │                                │
    │──────────────────────────────────► │                                │
    │                                    │  Store: messages/msg_001.toon  │
    │                                    │  Add to B's inbox              │
    │                                    │──────────────────────────────► │
    │                                    │                                │  Poll inbox
    │                                    │                                │  Read msg_001
    │                                    │  Mark delivered                │
    │                                    │◄────────────────────────────── │
    │                                    │                                │
    │  Ack delivered                     │                                │
    │◄────────────────────────────────── │                                │
```

### Pattern 2: Broadcast (Soldier → All)

```
Soldier Lead                  Exchange Layer              Soldier A  Soldier B  Soldier C
    │                              │                        │          │          │
    │ broadcast "pausing for dep"  │                        │          │          │
    │─────────────────────────────►│                        │          │          │
    │                              ├──► A's inbox           │          │          │
    │                              ├──► B's inbox                     │          │
    │                              ├──► C's inbox                                │
    │                              │                        │          │          │
    │                              │◄── ack A ──────────────│          │          │
    │                              │◄── ack B ────────────────────────│          │
    │                              │◄── ack C ───────────────────────────────────│
```

### Pattern 3: Shared Task List (Agent Teams pattern)

```
Lead                              Exchange Layer              Soldier A  Soldier B
  │                                    │                        │          │
  │ Write TASKS.toon:                  │                        │          │
  │  - task_001: "Design API"          │                        │          │
  │  - task_002: "Implement API"       │                        │          │
  │  - task_003: "Test API"            │                        │          │
  │──────────────────────────────────► │                        │          │
  │                                    │                        │          │
  │                                    │◄── Claim task_001 ─────│          │
  │                                    │                        │          │
  │                                    │◄── Claim task_002 ───────────────│
  │                                    │                        │          │
  │  See A claimed task_001            │                        │          │
  │  See B claimed task_002            │                        │          │
  │                                    │                        │          │
  │                                    │◄── A completes ────────│          │
  │                                    │  task_001 → results    │          │
  │                                    │                        │          │
  │  Verify task_001 output            │                        │          │
  │  Assign task_003 to A              │                        │          │
  │──────────────────────────────────► │──→ A's inbox ──────────│          │
```

### Pattern 4: Result Passing (Pipeline)

```
Soldier A (Architect)          Exchange Layer             Soldier B (Developer)
        │                           │                           │
        │ Write design doc          │                           │
        │ Send task to Task List    │                           │
        │──────────────────────────►│                           │
        │                           │  TASKS.toon:              │
        │                           │  task_001: "design.done"  │
        │                           │  └── result: path/to/doc  │
        │                           │                           │
        │                           │◄── Poll for task_001 ─────│
        │                           │  (task_001.depends_on     │
        │                           │   includes nothing)       │
        │                           │                           │
        │                           │── task_001 result ───────►│
        │                           │                           │
        │                           │                           │ B reads design doc
        │                           │                           │ B starts implementing
```

### Pattern 5: Adversarial Review

```
Soldier A (Builder)            Exchange Layer               Soldier R (Reviewer)
        │                           │                             │
        │ Submit work for review    │                             │
        │──────────────────────────►│                             │
        │                           │  Type: review_request        │
        │                           │─────→ R's inbox ───────────►│
        │                           │                             │
        │                           │                             │ R reads code
        │                           │                             │ R writes review
        │                           │◄── review_response ─────────│
        │                           │  Type: review_response       │
        │                           │  body: "issues: ..."         │
        │                           │                             │
        │◄── review_response ───────│                             │
        │                           │                             │
        │ A reads review            │                             │
        │ Fixes issues              │                             │
        │ Resubmits → cycle         │                             │
```

---

## 5. API Surface

### CLI Commands

| Command | Description |
|---|---|
| `hero exchange send <target> <message>` | Send a message to a soldier |
| `hero exchange listen [--block]` | Poll inbox for new messages |
| `hero exchange broadcast <message>` | Send to all active soldiers |
| `hero exchange status [--deploy <id>]` | Show exchange status |
| `hero exchange claim <task_id>` | Claim a task from the shared task list |
| `hero exchange complete <task_id>` | Mark a task as completed with result |
| `hero exchange purge` | Clean up completed exchanges |

### Integration Flags

| Flag | Effect |
|---|---|
| `hero deploy --targets X,Y --exchange` | Creates an exchange channel, spawns soldiers with exchange context |
| `hero spawn --sandbox X --task "..." --exchange <deploy_id>` | Attaches soldier to an existing exchange |
| `--exchange-timeout 3600` | Override default TTL for exchange messages |

### Python API

```python
from hero.exchange import ExchangeBroker, Message, TaskList

# Create an exchange
broker = ExchangeBroker(deploy_id="abc123")
broker.create_channel(soldiers=["a", "b", "c"], lead="lead_id")

# Send a message
broker.send(
    to="soldier_b",
    msg_type="direct",
    body="Please review the design doc at /path/doc.md"
)

# Poll inbox
messages = broker.poll_inbox(soldier_id="soldier_b")
for msg in messages:
    print(msg.body)
    broker.ack(msg.id)

# Shared task list
tasks = TaskList(deploy_id="abc123")
tasks.add(description="Implement login", depends_on=["task_002"])
tasks.claim(task_id="task_001", soldier_id="soldier_b")
tasks.complete(task_id="task_001", result="/path/output")
```

---

## 6. Integration Points

### SoldierSpawner Integration (`hero/soldier/spawner.py`)

When `--exchange` is passed, the spawner:
1. Registers the soldier in the exchange channel (CHANNEL.toon)
2. Injects exchange context into the soldier's brief:
   - Exchange ID
   - Inbox path (`~/.hero/exchange/<id>/queues/<soldier_id>_inbox/`)
   - Task list path (`~/.hero/exchange/<id>/TASKS.toon`)
   - Other soldier IDs (so it knows who to message)
3. Creates the soldier's inbox directory
4. Sets up heartbeat file for status tracking

### Deploy Integration (`hero/commands/deploy.py`)

```python
def deploy(targets, task, exchange=False):
    if exchange:
        broker = ExchangeBroker.create(
            soldiers=targets,
            lead=current_lead_id
        )
        for target in targets:
            spawner.launch(
                task=task,
                exchange_id=broker.deploy_id
            )
    else:
        # existing behavior
        for target in targets:
            spawner.launch(task=task)
```

### Go Integration (`hero/commands/go.py`)

`hero go --sandbox X --task Y --exchange`:
1. Lead spawns with full task description
2. Lead creates exchange channel
3. Lead breaks task into subtasks → writes TASKS.toon
4. Soldiers claim tasks from TASKS.toon
5. Soldiers communicate via exchange as needed
6. Lead monitors TASKS.toon for completion
7. Lead marks exchange complete → cleanup

### PipelineExecutor Integration

The PipelineExecutor already monitors soldier completion. When exchange is active:
- Add exchange status to pipeline manifest
- Verify agents can check review messages before finalizing
- Exchange status becomes part of the pipeline score

---

## 7. Delivery Guarantees & Edge Cases

### Delivery Semantics

| Property | Behavior |
|---|---|
| Delivery | At-least-once. Messages persist until `delivered_at` is set |
| Ordering | Best-effort within a thread_id. No global ordering |
| TTL | Default 3600s. Configurable via `--exchange-timeout` |
| Retry | Exponential backoff: 1s → 2s → 4s → 8s → max 60s. 5 attempts |
| Dead letter | After 5 failed delivery attempts → `~/.hero/dead_letter/exchange/` |
| Cleanup | Auto-purge exchanges where all soldiers have status=completed |

### Edge Cases

| Scenario | Handling |
|---|---|
| Soldier spawns but never polls inbox | TTL expiry → move to DLQ, alert Lead |
| Soldier completes mid-conversation | Pending messages to that soldier → re-route or DLQ |
| Lead crashes mid-deploy | Exchange persists on disk. `hero exchange status` shows last state. Lead can re-attach with `--exchange-id` |
| Duplicate message delivery | Messages are idempotent. Consumers check `id` before processing |
| Two soldiers claim same task | First claim wins. `claim()` is atomic (write + check) |
| Cross-sandbox communication | Supported. Exchange layer doesn't care about sandbox boundaries |
| Stale exchange directories | `hero exchange purge` or auto-purge after 24h |

### Retry Mechanism

```python
def send_with_retry(broker, message, max_attempts=5):
    for attempt in range(max_attempts):
        broker.send(message)
        try:
            broker.wait_for_ack(message.id, timeout=60)
            return True
        except TimeoutError:
            delay = 2 ** attempt  # exponential backoff
            time.sleep(delay)
    # All attempts failed → dead letter
    broker.send_to_dlq(message)
    return False
```

---

## 8. Comparison to Reference Systems

| Feature | HERO Exchange Layer | Claude Code Agent Teams | Gas Town |
|---|---|---|---|
| Storage | File-based (.toon) | In-memory (context window) | File-based + database |
| Message format | TOON files | Internal JSON | Unknown |
| Task list | Shared TASKS.toon | Shared task list | Mayor-managed queue |
| Inter-agent messaging | Direct + broadcast | Direct (peers msg each other) | Hierarchical (via mayor) |
| Delivery guarantees | At-least-once + DLQ | Best-effort | At-least-once |
| Persistence | Disk (survives restart) | Session-only | Disk |
| Retry | Exponential backoff | None | Linear backoff |
| TTL | Configurable | N/A | Configurable |
| Cleanup | Auto-purge on completion | Session end | Explicit destroy |
| Sandbox awareness | Cross-sandbox | Same session | Per-sandbox |

---

## 9. Implementation Plan

### Phase 1: Foundation (Core + Storage)

**Files to create:**
- `src/hero/exchange/__init__.py` — Package init, exports
- `src/hero/exchange/broker.py` — `ExchangeBroker` class (create channel, route messages)
- `src/hero/exchange/message.py` — `Message` dataclass, TOON serialization
- `src/hero/exchange/task_list.py` — `TaskList` class (shared task list management)
- `src/hero/exchange/models.py` — Data models: ChannelConfig, SoldierStatus, Thread

**Deliverable:**
- `ExchangeBroker.create(deploy_id, soldiers, lead)` → creates `~/.hero/exchange/<id>/`
- `ExchangeBroker.send(to, msg_type, body)` → writes `.toon` message, adds to inbox
- `ExchangeBroker.poll_inbox(soldier_id)` → returns list of pending messages
- `ExchangeBroker.ack(message_id)` → marks delivered/read
- `Message.to_toon()` / `Message.from_toon()` — serialization

### Phase 2: CLI Commands

**File to create/modify:**
- `src/hero/commands/exchange.py` — `hero exchange list|send|listen|broadcast|status|claim|complete|purge`
- `src/hero/cli.py` — Register exchange command group

**Deliverable:**
- `hero exchange status` shows active exchanges
- `hero exchange send soldier_b "hello"` sends direct message
- `hero exchange listen` polls inbox, prints new messages
- `hero exchange broadcast "warning"` sends to all
- `hero exchange claim task_001` / `hero exchange complete task_001`

### Phase 3: Integration with Spawner & Deploy

**Files to modify:**
- `src/hero/soldier/spawner.py` — Add `exchange_id` parameter to `launch()`, inject exchange context into soldier brief
- `src/hero/commands/deploy.py` — Add `--exchange` flag, create broker before spawning
- `src/hero/commands/go.py` — Add `--exchange` flag, Lead creates exchange + task list
- `src/hero/soldier/context.py` — Add exchange context block to `build_context()`

**Deliverable:**
- `hero deploy --targets X,Y --exchange` creates exchange channel
- Soldiers receive exchange context in their brief
- Soldiers can discover the exchange via environment or context file

### Phase 4: Shared Task List (Agent Teams Pattern)

**Files to create/modify:**
- `src/hero/exchange/task_list.py` — Full implementation with claim/complete/depends

**Deliverable:**
- Lead writes TASKS.toon with subtasks and dependencies
- Soldiers claim tasks atomically (first-claim-wins)
- Lead monitors task completion
- Dependency tracking: task_003 waits for task_002

### Phase 5: Reviewer / Adversarial Pattern

**Files to modify:**
- `src/hero/exchange/broker.py` — Add `review_request` / `review_response` message types
- `src/hero/commands/exchange.py` — Add `--review` flag or `hero exchange review`

**Deliverable:**
- Soldier A submits work for review via exchange
- Reviewer soldier reads the work and writes back issues
- Loop until reviewer approves or max cycles reached

### Phase 6: Cleanup & Reliability

**Files to create:**
- `src/hero/exchange/cleanup.py` — TTL expiry, stale exchange purge, DLQ integration

**Files to modify:**
- `src/hero/reliability/dlq.py` — Add exchange DLQ support
- `src/hero/soldier/spawner.py` — Auto-cleanup on soldier completion

**Deliverable:**
- TTL enforcement on stale messages
- Dead letter for undeliverable messages
- Auto-purge completed exchanges after 24h
- `hero exchange purge` manual cleanup

---

## 10. Migration Path

**Current state (before Exchange Layer):**
```
hero deploy --targets A,B,C --task "fix bugs"
  → spawns soldiers A, B, C in isolation
  → each soldier works independently
  → soldiers cannot coordinate or share results
```

**With `--exchange` flag:**
```
hero deploy --targets A,B,C --task "refactor auth" --exchange
  → Lead creates exchange channel
  → Lead writes TASKS.toon:
      - A: redesign auth schema
      - B: implement auth API (depends on A)
      - C: write auth tests (depends on B)
  → A claims task, works, completes
  → B claims task, reads A's output from task list, implements API
  → C claims task, reads B's output, writes tests
  → Lead monitors all tasks, marks exchange complete
```

**Backwards compatibility:**
- Without `--exchange`, behavior is identical to today
- Existing dispatch queue files are unchanged
- Exchange files live in their own directory (`~/.hero/exchange/`)
- No existing test needs modification

---

## Appendix: .toon Format Reference

The Exchange Layer uses the same TOON format as the rest of HERO:

```
# Key-value pairs
key: value
key: "quoted string"
key: null

# Nested
key:
  sub_key: value

# Lists
key[N]: item1, item2, item3

# Multiline (for message bodies)
key: |
  line 1
  line 2
  line 3
```

See `hero/state/toon.py` and `hero/soldier/dispatch.py` for existing TOON parsing/writing code.
