# HERO Resources & Integration Plan

> Research compilation for HERO — a CLI multi-agent orchestration system for Hermes.
> Date: 2025-05-23
> Status: v1.0 — initial discovery

---

## Table of Contents

1. [Hermes Agent Ecosystem](#1-hermes-agent-ecosystem)
2. [MCP Servers](#2-mcp-servers)
3. [Multi-Agent Orchestration](#3-multi-agent-orchestration)
4. [Agent Memory & Context](#4-agent-memory--context)
5. [Code Knowledge Graphs](#5-code-knowledge-graphs)
6. [Token Optimization](#6-token-optimization)
7. [CLI Frameworks](#7-cli-frameworks)
8. [Sandbox & Isolation](#8-sandbox--isolation)
9. [Integration Roadmap](#9-integration-roadmap)

---

## 1. Hermes Agent Ecosystem

### Official & Community Repos

| Repo | Stars | Description | HERO Relevance |
|------|-------|-------------|----------------|
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | — | Core Hermes Agent framework | **Core dependency** |
| [0xNyk/awesome-hermes-agent](https://github.com/0xNyk/awesome-hermes-agent) | 3,307 | Curated skills, tools, integrations | Skill discovery source |
| [NousResearch/hermes-agent-self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution) | 3,482 | DSPy + GEPA self-improvement | Could evolve HERO's skills |
| [outsourc-e/hermes-workspace](https://github.com/outsourc-e/hermes-workspace) | 4,715 | Web workspace — chat, terminal, memory, inspector | UI patterns to borrow |
| [farion1231/cc-switch](https://github.com/farion1231/cc-switch) | 78,509 | Desktop assistant for Claude Code, Codex, OpenClaw, Hermes | **Major competitor pattern** |
| [iOfficeAI/AionUi](https://github.com/iOfficeAI/AionUi) | 26,205 | 24/7 Cowork app for OpenClaw, Hermes, Claude Code, Codex, OpenCode | Coworking patterns |

### MiniMax AI / mmx-cli (User's Active Stack)

| Repo | Stars | Description | HERO Relevance |
|------|-------|-------------|----------------|
| [MiniMax-AI/cli](https://github.com/MiniMax-AI/cli) | 1,795 | Generate text, images, video, speech, and music | **User's primary AI CLI** |
| [zth0828/mmx-mcp-server](https://github.com/zth0828/mmx-mcp-server) | 32 | MCP server wrapper for MiniMax CLI | **MCP bridge for HERO** |
| [HZ6112/minimax-music-skills-v2](https://github.com/HZ6112/minimax-music-skills-v2) | 1 | Music generation skills for Claude Code via mmx | Skill template |
| [a2359117018/mmx-cli-skills](https://github.com/a2359117018/mmx-cli-skills) | 0 | Community skills built from minimax-cli | Skill examples |

**User's install:** `mmx-cli@1.0.11` globally via npm (`~/.npm-global/bin/mmx`)

**mmx capabilities:** text generation, image gen, video gen, speech/music, web search

**HERO integration idea:** Use `mmx` as a **soldier agent backend** — spawn mmx-based agents for creative tasks (music, images) within sandbox budgets. The MCP server (`zth0828/mmx-mcp-server`) exposes mmx as Hermes-compatible tools.

### Already Installed

- **agent-skills** (`~/.hermes/skills/agent-skills/`) — 23 skills from addyosmani/agent-skills, converted to Hermes format
- **graphify** (`~/.local/bin/graphify`) — Code knowledge graph generator; Hermes rules installed in AGENTS.md

---

## 2. MCP Servers

### Official Reference Servers

| Server | Language | Purpose | HERO Use |
|--------|----------|---------|----------|
| [Filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | TypeScript | Secure file ops with access controls | **Sandbox file access** |
| [Git](https://github.com/modelcontextprotocol/servers/tree/main/src/git) | Python | Read, search, manipulate Git repos | **Project state tracking** |
| [Memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | TypeScript | Knowledge graph-based persistent memory | **Katana integration** |
| [Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) | TypeScript | Web content fetching for LLMs | Research agent tool |
| [Sequential Thinking](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking) | TypeScript | Dynamic reflective problem-solving | **Lead agent reasoning** |
| [Time](https://github.com/modelcontextprotocol/servers/tree/main/src/time) | TypeScript | Time/timezone conversion | Utility |

### Archived (Still Useful)

| Server | Purpose | HERO Use |
|--------|---------|----------|
| [GitHub](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/github) | Repo management, API integration | PR automation |
| [PostgreSQL](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres) | Read-only DB access | Telemetry/logging |
| [SQLite](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite) | Database interaction | Local state store |
| [Puppeteer](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/puppeteer) | Browser automation | Web testing agents |

### MCP Ecosystem Tools

| Tool | Stars | Purpose | HERO Use |
|------|-------|---------|----------|
| [mcp-cli](https://github.com/wong2/mcp-cli) | — | CLI inspector for MCP | Debug MCP integration |
| [mcp-get](https://mcp-get.com) | — | Install/manage MCP servers | Dependency management |
| [MCPHub](https://github.com/Jeamee/MCPHub-Desktop) | — | GUI for discovering, installing MCP servers | User-friendly setup |
| [FastMCP](https://github.com/punkpeye/fastmcp) | — | TypeScript framework for MCP servers | Build custom HERO MCP server |
| [mcpm.sh](https://mcpm.sh) | — | Homebrew-like MCP server manager | Package management |

### Integration Plan

1. **Phase 2**: Configure `Filesystem` + `Git` MCP servers for each sandbox
2. **Phase 4**: Use `Memory` MCP server as alternative KATANA backend
3. **Phase 5**: Build custom HERO MCP server exposing `hero query`, `hero dispatch`, `hero status`
4. **Hermes config**: Register MCP servers per-sandbox in `~/.hermes/config.yaml`

---

## 3. Multi-Agent Orchestration

### Frameworks & Patterns

| Repo | Stars | Description | HERO Relevance |
|------|-------|-------------|----------------|
| [openai/swarm](https://github.com/openai/swarm) | 21,520 | Lightweight multi-agent orchestration by OpenAI | **Pattern model** — handoffs, routing |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework) | 10,665 | Build, orchestrate, deploy AI agents (Python/.NET) | Enterprise patterns |
| [kyegomez/swarms](https://github.com/kyegomez/swarms) | 6,728 | Enterprise-grade production multi-agent framework | Scale patterns |
| [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm) | 4,409 | Reliable multi-agent orchestration | Agent role definitions |
| [SolaceLabs/solace-agent-mesh](https://github.com/SolaceLabs/solace-agent-mesh) | 4,442 | Event-driven multi-agent framework | Event bus for HERO |
| [swarmclawai/swarmclaw](https://github.com/swarmclawai/swarmclaw) | 518 | Open-source agent runtime — memory, MCP, schedules, delegation | **Closest to HERO vision** |
| [BUPT-GAMMA/MASFactory](https://github.com/BUPT-GAMMA/MASFactory) | 389 | Graph-centric multi-agent orchestration | Graph-based dispatch |

### Key Patterns to Adopt

1. **Swarm Handoffs** (OpenAI): Lightweight agent-to-agent routing without heavy framework
2. **Event-Driven Mesh** (Solace): Agents communicate via events, not direct calls
3. **Agency Roles** (agency-swarm): CEO, Developer, Reviewer role templates
4. **Agent Memory + MCP** (swarmclaw): Combines all our needs into one reference

### HERO's Unique Angle

Unlike these frameworks, HERO is:
- **Sandbox-first**: Token budget is the gatekeeper, not an afterthought
- **Graph-native**: Uses graphify for code navigation instead of loading full repos
- **TOON-native**: Internal state serialized in token-efficient format
- **Hermes-native**: Built specifically for Hermes primitives (delegate_task, cronjob, skills)

---

## 4. Agent Memory & Context

### Memory Systems

| Repo | Stars | Description | HERO Relevance |
|------|-------|-------------|----------------|
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | 56,477 | Universal memory layer for AI Agents | **KATANA alternative** |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | 24,538 | Context database for AI agents — hierarchical context delivery | **Advanced KATANA** |
| [memvid/memvid](https://github.com/memvid/memvid) | 15,551 | Serverless single-file memory layer | Lightweight memory |
| [langchain-ai/langmem](https://github.com/langchain-ai/langmem) | 1,464 | LangChain memory framework | Memory patterns |
| [TeleAI-UAGI/Awesome-Agent-Memory](https://github.com/TeleAI-UAGI/Awesome-Agent-Memory) | 427 | Curated papers on agent memory | Research reference |

### Context Management

| Repo | Stars | Description | HERO Use |
|------|-------|-------------|----------|
| [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) | 6,211 | Prompt compression (up to 20x) | Pre-flight compression |
| [OnlyTerp/openclaw-optimization-guide](https://github.com/OnlyTerp/openclaw-optimization-guide) | 322 | Speed, memory, context management guide | Best practices |

### Integration Plan

1. **Phase 4**: Implement KATANA as simple `MEMORY.md` per sandbox (current plan)
2. **Phase 5**: Optional upgrade to mem0 for cross-sandbox memory
3. **Phase 6**: Add LLMLingua integration for prompt compression before agent spawn
4. **Research**: OpenViking's hierarchical context model for advanced use cases

---

## 5. Code Knowledge Graphs

### Existing Tools

| Repo | Stars | Description | HERO Relevance |
|------|-------|-------------|----------------|
| [giancarloerra/SocratiCode](https://github.com/giancarloerra/SocratiCode) | 2,722 | Enterprise codebase intelligence — 61% less tokens, 84% fewer calls | **Competitor analysis** |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) | 25,502 | Incremental parsing system | Parser backend |
| [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep) | 14,078 | Structural search, lint, rewriting | Code querying |
| [sdsrss/code-graph-mcp](https://github.com/sdsrss/code-graph-mcp) | 33 | AST knowledge graph MCP server for Claude Code | MCP-native graph |
| [NeuralRays/codexray](https://github.com/NeuralRays/codexray) | 5 | Semantic knowledge graph & MCP server — 30%+ token savings | Similar to graphify |
| [codeprysm/codeprysm](https://github.com/codeprysm/codeprysm) | 3 | Graph-based code intelligence with MCP server | Graph + MCP |

### graphify (Already Adopted)

- **Binary**: `~/.local/bin/graphify`
- **Commands**: `query`, `path`, `explain`, `update`, `watch`, `tree`, `benchmark`
- **Integration**: Hermes rules in `/home/max/Max_Hermes/AGENTS.md`
- **Performance**: sook_pro ~600K tokens (raw) → ~50K tokens (graph)
- **TOON savings**: Graph nodes 53.6% smaller in TOON

### Integration Plan

1. **Current**: Use graphify for pre-flight file discovery (replaces grep)
2. **Phase 2**: Auto-run `graphify update .` after code changes in sandbox
3. **Phase 3**: Cache graph queries in TOON format for repeated lookups
4. **Future**: Evaluate ast-grep for structural code rewriting (soldier auto-fixes)

---

## 6. Token Optimization

### Formats & Techniques

| Resource | Type | Description | HERO Use |
|----------|------|-------------|----------|
| [TOON Format](https://github.com/toon-format) | Format | Token-Oriented Object Notation | **Native state format** |
| [KDnuggets: TOON vs JSON](https://www.kdnuggets.com/) | Article | 50%+ token reduction for LLM data | Rationale documented |
| [microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) | Tool | Prompt compression up to 20x | Pre-flight compression |
| [memvid/memvid](https://github.com/memvid/memvid) | Tool | Serverless memory layer | Lightweight context |

### TOON Test Results (HERO Internal)

| Data Type | JSON | TOON | Savings |
|-----------|------|------|---------|
| Sandbox INDEX | 502 bytes | 201 bytes | **60.0%** |
| Budget metadata | 593 bytes | 438 bytes | **26.1%** |
| Graph nodes (5) | 1,176 bytes | 546 bytes | **53.6%** |
| **Projected full graph** | 361 KB | ~170 KB | **191 KB saved** |

### HERO Token Budgets (from SAMB Constitution)

| Sandbox | Bootstrap Max | Notes |
|---------|---------------|-------|
| QLearner | 8,000 chars | Learning app |
| SOOK Pro | 8,000 chars | Production app |
| H.E.R | 6,000 chars | Assistant app |
| Freya | 5,000 chars | Backend service |
| Default | 5,000 chars | New sandboxes |

### Pre-Flight Formula

```
estimated_tokens = ~5,000 base_overhead + (total_lines / 100 * 2,000)
max_per_flash_soldier = 20,000 tokens
max_per_thinking_model = 10,000 tokens
soldiers_needed = ceil(files_to_touch / 2)
```

---

## 7. CLI Frameworks

### Python Stack for HERO

| Repo | Stars | Description | HERO Use |
|------|-------|-------------|----------|
| [Textualize/rich](https://github.com/Textualize/rich) | 56,422 | Rich text and beautiful terminal formatting | **Output styling** |
| [Textualize/textual](https://github.com/Textualize/textual) | 35,997 | TUI framework — terminal + web browser | **Interactive TUI** |
| [tiangolo/typer](https://github.com/fastapi/typer) | 19,458 | CLI framework based on Python type hints | **Command structure** |
| [pallets/click](https://github.com/pallets/click) | 17,508 | Composable CLI toolkit | Alternative to Typer |
| [willmcgugan/rich-cli](https://github.com/Textualize/rich-cli) | 3,668 | CLI toolbox for fancy terminal output | Utility commands |

### HERO CLI Design

```
hero scan                    # Auto-discover projects → create sandboxes
hero sandbox create <name>   # New sandbox with budget + skills
hero sandbox enter <name>    # Spawn agent within sandbox
hero sandbox freeze <name>   # Archive to TOON + MEMORY.md
hero dispatch <task>         # Lead → Soldiers within budget
hero status                  # All sandboxes + budgets + active agents
hero query "<question>"      # Graphify query across all projects
hero katana update           # Force checkpoint all active sandboxes
```

---

## 8. Sandbox & Isolation

### Tools

| Repo | Stars | Description | HERO Use |
|------|-------|-------------|----------|
| [e2b-dev/E2B](https://github.com/e2b-dev/E2B) | 12,331 | Secure environment with real-world tools for agents | **Cloud sandbox option** |
| [containers/bubblewrap](https://github.com/containers/bubblewrap) | 7,333 | Low-level unprivileged sandboxing | Local process isolation |

### HERO Sandbox Model

HERO sandboxes are **logical**, not containerized:

```
~/.hero/sandboxes/
├── INDEX.toon
├── sook-pro/
│   ├── BUDGET.toon       # Hard token cap
│   ├── SKILLS.list       # Approved skills only
│   ├── MEMORY.toon       # Katana checkpoint
│   ├── HEARTBEAT.toon    # Pending tasks
│   └── code/             # Symlinks to project
└── her/
    └── ...
```

**Future**: Optional Docker/bubblewrap integration for untrusted code execution.

---

## 9. Integration Roadmap

### Phase 0: Foundation (Now)
- [ ] Scaffold `~/Development/HERO/` project
- [ ] Choose CLI framework: **Typer + Rich** (type-safe + beautiful output)
- [ ] Define TOON schema for all state files
- [ ] Implement `hero scan` — auto-discover `~/Development/` projects

### Phase 1: Sandbox Engine
- [ ] `hero sandbox create/enter/freeze`
- [ ] `BUDGET.toon` enforcement
- [ ] `SKILLS.list` validation against `~/.hermes/skills/`
- [ ] Progressive loader (symlinks → copy-on-write)

### Phase 2: Project Scanner + Graphify
- [ ] Auto-generate `SMI_INDEX.toon` from `~/Development/`
- [ ] Integrate `graphify query` for pre-flight discovery
- [ ] Auto-run `graphify update .` post-change
- [ ] Cache graph traversals in TOON

### Phase 3: Constitution + Pre-Flight Gate
- [ ] Load `CONSTITUTION.md` rules per sandbox
- [ ] Pre-flight token calculation before spawn
- [ ] Auto-split tasks over budget
- [ ] Enforce `estimated_tokens = 5k + (lines/100 * 2k)`

### Phase 4: Dispatcher (Lead → Soldiers)
- [ ] Lead agent spawn with sandbox context
- [ ] Soldier spawn within budget (max 2 files per Flash)
- [ ] `delegate_task` integration (3 parallel max)
- [ ] Result aggregation back to Lead

### Phase 5: KATANA Checkpoints
- [ ] 70% context threshold trigger
- [ ] `MEMORY.toon` auto-update (distilled, no logs)
- [ ] Compaction #3 → ARCHIVE protocol
- [ ] Archivist agent for memory compression

### Phase 6: NUEMR Integration
- [ ] `nuemr index` on `~/.hermes/skills/`
- [ ] `nuemr search` for intent-to-skill matching
- [ ] Hybrid search: NUEMR semantic + keyword fallback

### Phase 7: Advanced Features
- [ ] MCP server: `hero-mcp` exposing tools
- [ ] `mmx-mcp-server` integration for creative agent soldiers
- [ ] `cronjob` scheduled patrols
- [ ] LLMLingua prompt compression
- [ ] Optional mem0 cross-sandbox memory

---

## Quick Reference Links

### Hermes
- Main repo: https://github.com/NousResearch/hermes-agent
- Awesome list: https://github.com/0xNyk/awesome-hermes-agent
- Self-evolution: https://github.com/NousResearch/hermes-agent-self-evolution

### MCP
- Official servers: https://github.com/modelcontextprotocol/servers
- Registry: https://registry.modelcontextprotocol.io/
- Python SDK: https://github.com/modelcontextprotocol/python-sdk

### mmx-cli (MiniMax AI)
- Official CLI: https://github.com/MiniMax-AI/cli
- MCP Server: https://github.com/zth0828/mmx-mcp-server
- Music Skills: https://github.com/HZ6112/minimax-music-skills-v2
- npm: `npm install -g mmx-cli`

### Multi-Agent
- OpenAI Swarm: https://github.com/openai/swarm
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- Agency Swarm: https://github.com/VRSEN/agency-swarm

### Memory
- mem0: https://github.com/mem0ai/mem0
- OpenViking: https://github.com/volcengine/OpenViking
- LLMLingua: https://github.com/microsoft/LLMLingua

### Code Intelligence
- graphify: Already installed (`~/.local/bin/graphify`)
- Tree-sitter: https://github.com/tree-sitter/tree-sitter
- ast-grep: https://github.com/ast-grep/ast-grep
- SocratiCode: https://github.com/giancarloerra/SocratiCode

### CLI
- Typer: https://github.com/fastapi/typer
- Rich: https://github.com/Textualize/rich
- Textual: https://github.com/Textualize/textual

### TOON
- CLI: `npx @toon-format/cli`
- Article: KDnuggets "TOON: Token-Oriented Object Notation"

---

## 10. Design Resources

### Icon Libraries

| Repo | Stars | Description | HERO Use |
|------|-------|-------------|----------|
| [feathericons/feather](https://github.com/feathericons/feather) | 25,920 | Simply beautiful open-source icons | CLI output icons |
| [tailwindlabs/heroicons](https://github.com/tailwindlabs/heroicons) | 23,544 | Free MIT-licensed high-quality SVG icons | UI components |
| [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | 22,715 | Beautiful & consistent icon toolkit (Feather fork) | Default icon set |
| [tabler/tabler-icons](https://github.com/tabler/tabler-icons) | 20,775 | 6000+ free MIT-licensed SVG icons | Extended icon library |
| [phosphor-icons/homepage](https://github.com/phosphor-icons/homepage) | 6,762 | Flexible icon family with multiple weights | TUI variations |

### UI Frameworks & Design Systems

| Repo | Stars | Description | HERO Use |
|------|-------|-------------|----------|
| [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | 114,890 | Beautifully-designed accessible components | Web dashboard reference |
| [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | 95,092 | Utility-first CSS framework | Styling foundation |
| [rose-pine/rose-pine-theme](https://github.com/rose-pine/rose-pine-theme) | 1,571 | All natural pine, faux fur, soho vibes | Terminal color scheme |
| [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) | 10,564 | Fluent System Icons from Microsoft | Cross-platform icons |

### Flutter Design (User's Stack)

| Resource | Type | Description | HERO Use |
|----------|------|-------------|----------|
| [Flutter Material](https://docs.flutter.dev/ui/widgets/material) | Docs | Official Material Design widgets for Flutter | SOOK/H.E.R UI reference |
| [fluttergems.dev](https://fluttergems.dev) | Registry | Curated Flutter packages | Package discovery |

### Terminal Aesthetics

| Tool | Purpose | HERO Integration |
|------|---------|------------------|
| **Rich** (Textualize) | Rich text & formatting | Already in CLI stack |
| **Textual** (Textualize) | TUI framework | Interactive HERO dashboard |
| **Rose Pine** | Color theme | Terminal color palette |
| **Nerd Fonts** | Patched developer fonts | Terminal icon support |

### HERO Design Decisions

- **CLI aesthetic**: Minimal, military-grade precision (matching HERO name)
- **Color scheme**: Rose Pine Moon (dark, sophisticated, low eye strain)
- **Icons**: Lucide (clean, consistent, Feather heritage)
- **Progress bars**: Rich progress with custom styling
- **Tables**: Rich tables with alternating rows
- **Status indicators**: Colored dots + Lucide icons

---

*Document compiled from GitHub API searches, README extractions, and HERO internal testing.*
*Next step: Begin Phase 0 — scaffold HERO project with Typer + Rich.*
