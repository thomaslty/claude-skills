# Claude Code Custom Skills

Custom slash commands and plugins for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Components

### Skills

Skills live in `skills/`. Copy to install:

```bash
cp -r skills/explore ~/.claude/skills/explore
cp -r skills/no-code-change ~/.claude/skills/no-code-change
cp -r skills/propose ~/.claude/skills/propose
cp -r skills/review ~/.claude/skills/review
```

| Skill | Description |
|-------|-------------|
| [/explore](skills/explore/) | Read-only thinking partner — explore ideas, plan approaches, and stress-test designs without touching code |
| [/no-code-change](skills/no-code-change/) | Show-first workflow — gather, summarize, and present before making any changes |
| [/propose](skills/propose/) | Sequential 3-agent pipeline (explore, engineer, verify) — vetted solution proposals with online fact-checking, read-only |
| [/review](skills/review/) | Comprehensive code review with 6 parallel sub-agents (quality, reuse, truthfulness, efficiency, security, best practices) |

### Commands

Slash commands live in `commands/`. Copy to install:

```bash
cp commands/commit.md ~/.claude/commands/commit.md
cp -r commands/dev ~/.claude/commands/dev
cp -r commands/hfv ~/.claude/commands/hfv
```

| Command | Description |
|---------|-------------|
| `/commit` | Git commits without the Co-Authored-By trailer |

#### `dev:` — development lifecycle and code review

| Command | Description |
|---------|-------------|
| `/dev:help` | Quick-reference card for the `dev:` namespace |
| `/dev:development-guideline` | Mandatory methodology — proposal-driven, TDD backend, visual-driven frontend |
| `/dev:parallel-development` | Build multiple proposals at once via per-worktree parallel sub-agents |
| `/dev:finishing-development` | Archive change, commit, push, then merge back into the target branch |
| `/dev:full-development-cycle` | End-to-end: proposal → implementation → merged and pushed |
| `/dev:code-review` | Review the diff for correctness and quality (logic, readability, reuse, efficiency) |
| `/dev:security-review` | Review for vulnerabilities (injection, secrets, auth gaps, CVEs, data exposure) |
| `/dev:simplify` | Review for over-engineering — what to delete or replace with stdlib |
| `/dev:full-review` | Comprehensive review across every lens in one synthesized report |
| `/dev:debt` | Harvest `ponytail:` / TODO / FIXME / HACK markers into a debt ledger |

#### `hfv:` — Hypothesis-Fix-Verify debugging

| Command | Description |
|---------|-------------|
| `/hfv:full` | Full systematic debugging cycle |
| `/hfv:hypothesis` | Deep exploration and hypothesis formation only |
| `/hfv:validate-hypothesis` | Validate hypothesis with parallel sub-agents (code review + online research) |
| `/hfv:fix` | Implement minimal targeted fix for an accepted hypothesis |
| `/hfv:archive` | Archive a verified fix as resolved |

## Structure

```
claude-skills/
├── skills/                # Skills (/<name>)
│   ├── explore/
│   ├── no-code-change/
│   ├── propose/
│   └── review/
└── commands/              # Slash commands (/<name> or /<group>:<name>)
    ├── commit.md
    ├── dev/
    │   ├── development-guideline.md
    │   ├── parallel-development.md
    │   ├── finishing-development.md
    │   ├── full-development-cycle.md
    │   ├── code-review.md
    │   ├── security-review.md
    │   ├── simplify.md
    │   ├── full-review.md
    │   ├── debt.md
    │   └── help.md
    └── hfv/
        ├── full.md
        ├── hypothesis.md
        ├── validate-hypothesis.md
        ├── fix.md
        └── archive.md
```
