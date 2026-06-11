# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Prompt Template System

HERO's agent prompts are external `.md` files, not hardcoded Python strings.

**Override location:** `~/.hero/prompts/`
**Bundled defaults:** `src/hero/prompts/defaults/`

### Quick edits

```bash
# Change what soldiers are told to do
vim ~/.hero/prompts/roles/soldier.md

# Add TDD enforcement to all agents
vim ~/.hero/prompts/rules/tdd.md

# Change verify phase instructions
vim ~/.hero/prompts/phases/verify.md
```

### Template variables

Templates use `$variable` syntax. Available variables per template:

**roles/soldier.md:** `$sandbox`, `$workdir`, `$model`, `$context_window`, `$max_tokens`, `$budget`, `$task`, `$extra_rules`

**phases/verify.md:** `$sandbox`, `$original_task`, `$checks`

**phases/fix.md:** `$sandbox`, `$task`, `$verify_task_id`

**phases/archive.md:** `$sandbox`, `$task`, `$sandbox_path`, `$date`, `$date_time`, `$task_short`

### Adding a project-specific override

```bash
mkdir -p ~/.hero/prompts/projects/my-app/roles
cp ~/.hero/prompts/roles/soldier.md ~/.hero/prompts/projects/my-app/roles/soldier.md
# Edit the copy — it will be used for my-app sandbox only
```

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
