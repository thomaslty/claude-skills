# Claude Code Custom Skills

Custom slash commands and plugins for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Components

### Commands

Slash commands live in `commands/`. Copy to install:

```bash
cp commands/commit.md ~/.claude/commands/commit.md
```

| Command | Description |
|---------|-------------|
| `/commit` | Git commits without the Co-Authored-By trailer |

### Plugins

Plugins live in `plugins/`. Each has its own README with install instructions.

| Plugin | Description |
|--------|-------------|
| [hfv](plugins/hfv/) | Hypothesis-Fix-Verify — systematic debugging with `hfv:full`, `hfv:hypothesis`, `hfv:fix`, `hfv:archive` |

## Structure

```
claude-skills/
├── commands/              # Slash commands (/<name>)
│   └── commit.md
└── plugins/               # Plugins (<plugin>:<skill>)
    └── hfv/
```
