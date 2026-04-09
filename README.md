# Claude Code Custom Skills

A collection of custom skills, plugins, and slash commands for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

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

### `hfv` — Systematic Debugging (Plugin)

A plugin with sub-skills for each phase of the HFV debugging workflow. Auto-triggered by Claude when it detects a debugging scenario, or invoked explicitly with colon notation:

| Command | Purpose |
|---------|---------|
| `hfv:full` | Run the full hypothesis -> fix -> verify cycle |
| `hfv:hypothesis` | Deep exploration and hypothesis formation only (no code changes) |
| `hfv:fix` | Implement a fix for an accepted hypothesis |
| `hfv:archive` | Archive a verified fix as successfully resolved |

Best for:
- Failures that can't be reproduced locally
- Issues requiring manual verification in a real environment (staging, production, remote infra)
- Multi-layered problems with potentially independent causes
- Bugs where trial-and-error would waste deploy cycles without structure

## Installation

### Slash commands

Symlink into your Claude Code config so updates to this repo are picked up automatically:

```bash
ln -s "$(pwd)/commands/commit.md" ~/.claude/commands/commit.md
ln -s "$(pwd)/commands/hypothesis-fix-verify.md" ~/.claude/commands/hypothesis-fix-verify.md
```

### HFV plugin

The `hfv` skill is a Claude Code plugin. Register it by adding an entry to the `plugins` object in `~/.claude/plugins/installed_plugins.json`:

```json
"hfv@local": [
  {
    "scope": "user",
    "installPath": "<absolute-path-to-this-repo>/skills/hfv",
    "version": "1.0.0",
    "installedAt": "<current-ISO-date>"
  }
]
```

Then restart Claude Code. The `hfv:full`, `hfv:hypothesis`, `hfv:fix`, and `hfv:archive` skills will be available.

## Structure

```
claude-skills/
├── commands/                              # Slash commands (user-invoked with /<name>)
│   ├── commit.md                          # /commit
│   └── hypothesis-fix-verify.md           # /hypothesis-fix-verify
└── skills/
    └── hfv/                               # Plugin (colon notation: hfv:<skill>)
        ├── package.json                   # Plugin name: "hfv"
        ├── .claude-plugin/
        │   └── plugin.json                # Plugin metadata
        └── skills/
            ├── full/SKILL.md              # hfv:full — complete cycle
            ├── hypothesis/SKILL.md        # hfv:hypothesis — explore + hypothesize only
            ├── fix/SKILL.md               # hfv:fix — implement fix + stop
            └── archive/SKILL.md           # hfv:archive — archive resolved issue
```

**Commands vs Plugins:**

| | Commands (`commands/`) | Plugins (`skills/<name>/`) |
|---|---|---|
| **Trigger** | User types `/<name>` | Claude auto-triggers or user types `<plugin>:<skill>` |
| **Format** | Single `.md` file | Plugin directory with `package.json` + `skills/` subdirectories |
| **Sub-commands** | No | Yes, via colon notation (`hfv:full`, `hfv:fix`) |
| **Key fields** | `description`, `allowed-tools`, `argument-hint` | `name`, `description` in each SKILL.md |
| **Use case** | Explicit workflows you want on demand | Structured workflows with distinct phases |

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

### Plugin with sub-skills

Create a plugin directory with the following structure:

```
skills/<plugin-name>/
├── package.json                    # { "name": "<plugin-name>", "version": "1.0.0", "type": "module" }
├── .claude-plugin/
│   └── plugin.json                 # Plugin metadata (name, description, author, keywords)
└── skills/
    └── <skill-name>/
        └── SKILL.md                # Invoked as <plugin-name>:<skill-name>
```

Each `SKILL.md` uses frontmatter:

```yaml
---
name: skill-name
description: When Claude should auto-trigger this skill
---

Full skill instructions.
```
