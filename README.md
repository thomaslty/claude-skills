# Claude Code Custom Skills

A collection of custom skills and slash commands for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Skills

### `/commit` — Clean Git Commits

Creates git commits without the `Co-Authored-By` trailer. Analyzes staged/unstaged changes, follows existing commit style, and drafts concise commit messages.

**Usage:**
```
/commit
```

### `/hypothesis-fix-verify` — Systematic Debugging (Slash Command)

Disciplined debugging workflow: one hypothesis, one fix, one verification — then stop. Prevents the common mistake of stacking multiple unverified fixes. Writes hypothesis artifacts to `hfv/` in your project directory.

**Usage:**
```
/hypothesis-fix-verify TLS handshake failing after JDK upgrade
```

### `hfv` — Systematic Debugging (Model-Invoked Skill)

The same HFV workflow, but auto-triggered by Claude when it detects a debugging scenario that fits. Also supports sub-commands:

| Command | Purpose |
|---------|---------|
| `/hfv:full` | Run the full hypothesis -> fix -> verify cycle |
| `/hfv:hypothesis` | Deep exploration and hypothesis formation only (no code changes) |
| `/hfv:fix` | Implement a fix for an accepted hypothesis |
| `/hfv:archive` | Archive a verified fix as successfully resolved |

Best for:
- Failures that can't be reproduced locally
- Issues requiring manual verification in a real environment (staging, production, remote infra)
- Multi-layered problems with potentially independent causes
- Bugs where trial-and-error would waste deploy cycles without structure

## Installation

### Option 1: Symlink (recommended)

Symlink into your Claude Code config so updates to this repo are picked up automatically:

```bash
# Slash commands
ln -s "$(pwd)/commands/commit.md" ~/.claude/commands/commit.md
ln -s "$(pwd)/commands/hypothesis-fix-verify.md" ~/.claude/commands/hypothesis-fix-verify.md

# Model-invoked skills
ln -s "$(pwd)/skills/hfv" ~/.claude/skills/hfv
```

### Option 2: Copy

Copy the files directly:

```bash
# Slash commands
cp commands/*.md ~/.claude/commands/

# Model-invoked skills
cp -r skills/* ~/.claude/skills/
```

## Structure

```
claude-skills/
├── commands/                              # Slash commands (user-invoked with /<name>)
│   ├── commit.md                          # /commit
│   └── hypothesis-fix-verify.md           # /hypothesis-fix-verify
└── skills/                                # Model-invoked skills (auto-triggered by Claude)
    └── hfv/
        └── SKILL.md                       # Auto-triggers + sub-commands
```

**Commands vs Skills:**

| | Commands (`commands/`) | Skills (`skills/`) |
|---|---|---|
| **Trigger** | User types `/<name>` | Claude auto-triggers based on task context |
| **Format** | Single `.md` file | `<name>/SKILL.md` directory |
| **Key fields** | `description`, `allowed-tools`, `argument-hint` | `name`, `description` |
| **Use case** | Explicit workflows you want on demand | Behaviors Claude should adopt automatically |

## Adding New Skills

### Slash command

Create `commands/<name>.md` with frontmatter:

```yaml
---
description: Short description shown in /help
allowed-tools: Bash, Read, Glob, Grep
argument-hint: <required> [optional]
---

Instructions for Claude to follow when this command is invoked.
```

### Model-invoked skill

Create `skills/<name>/SKILL.md` with frontmatter:

```yaml
---
name: skill-name
description: When Claude should auto-trigger this skill
---

Full skill instructions.
```
