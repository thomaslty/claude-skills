# Claude Code Custom Skills

Custom slash commands and plugins for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Components

### Skills

Skills live in `skills/`. Copy to install:

```bash
cp -r skills/review ~/.claude/skills/review
```

| Skill | Description |
|-------|-------------|
| [/review](skills/review/) | Show-first workflow — gather, summarize, and present before making any changes |

### Commands

Slash commands live in `commands/`. Copy to install:

```bash
cp commands/commit.md ~/.claude/commands/commit.md
cp -r commands/hfv ~/.claude/commands/hfv
```

| Command | Description |
|---------|-------------|
| `/commit` | Git commits without the Co-Authored-By trailer |
| `/hfv:full` | Hypothesis-Fix-Verify — full systematic debugging cycle |
| `/hfv:hypothesis` | Deep exploration and hypothesis formation only |
| `/hfv:validate-hypothesis` | Validate hypothesis with parallel sub-agents (code review + online research) |
| `/hfv:fix` | Implement minimal targeted fix for an accepted hypothesis |
| `/hfv:archive` | Archive a verified fix as resolved |

## Structure

```
claude-skills/
├── skills/                # Skills (/<name>)
│   └── review/
└── commands/              # Slash commands (/<name> or /<group>:<name>)
    ├── commit.md
    └── hfv/
        ├── full.md
        ├── hypothesis.md
        ├── validate-hypothesis.md
        ├── fix.md
        └── archive.md
```
