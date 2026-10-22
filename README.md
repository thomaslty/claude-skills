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
cp commands/show-plan.md ~/.claude/commands/show-plan.md
cp commands/fable-design-opus-execute.md ~/.claude/commands/fable-design-opus-execute.md
cp -r commands/dev ~/.claude/commands/dev
cp -r commands/hfv ~/.claude/commands/hfv
cp agents/*.md ~/.claude/agents/
mkdir -p ~/.claude/templates && cp -r templates/dev ~/.claude/templates/dev
mkdir -p ~/.claude/scripts && cp -r scripts/dev ~/.claude/scripts/dev
```

The `dev:1-design` … `dev:full-dev-cycle` commands need the `agents/` (one fresh agent per phase) and `templates/dev/` (the decision page) copies too.

| Command | Description |
|---------|-------------|
| `/commit` | Git commits without the Co-Authored-By trailer |
| `/show-plan` | Show the full current plan — goal, dependency graph, matrix table, worked detail per step |
| `/fable-design-opus-execute` | Fable designs in the main session; Opus sub-agents execute the code |

#### `dev:` — development lifecycle and code review

| Command | Description |
|---------|-------------|
| `/dev:help` | Quick-reference card for the `dev:` namespace |
| `/dev:development-guideline` | Mandatory methodology — proposal-driven, TDD backend, visual-driven frontend |
| `/dev:parallel-development` | Build multiple proposals at once via per-worktree parallel sub-agents |
| `/dev:finishing-development` | Archive, then land each repo by its own `.claude/finishing-development.md`; asks for the rules first when a repo has none |
| `/dev:ticket` | Orca board ticket — `new` makes a card + worktree, `start` launches Claude on it |
| `/dev:1-design` | Fresh agent writes `plan/<slug>/plan.md`, asks you via a decision-tree HTML page |
| `/dev:2-implement` | Fresh agent follows the plan under the guideline until every step is verified |
| `/dev:3-review` | 4 fresh reviewers (correctness, security, feature, completeness), T0 only, HTML page |
| `/dev:full-dev-cycle` | Design ⏸ → implement → review ⏸ → fix, each phase a fresh agent, stops for you after design and review |
| `/dev:learn-conventions` | Merge learned coding conventions into `.claude/conventions.md` |
| `/dev:code-review` | Review the diff for correctness and quality (logic, readability, reuse, efficiency) |
| `/dev:security-review` | Review for vulnerabilities (injection, secrets, auth gaps, CVEs, data exposure) |
| `/dev:simplify` | Review for over-engineering — what to delete or replace with stdlib |
| `/dev:full-review` | Comprehensive review across every lens in one synthesized report |
| `/dev:investigate` | Answer an open question — cited evidence, ranked hypotheses, refute the leader (read-only) |
| `/dev:create-readme` | Write or rewrite a README — 9 sections, at most 5 benefit-framed features, config table with a Required column |
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
├── agents/                # Phase agents for dev: (designer, implementer, reviewer, convention-learner)
├── templates/dev/         # Decision page HTML + build-page.py
├── scripts/dev/           # ticket-source, orca-card, plan-status, decision-page, review-page, screen-css, chrome-devtools-unlock
├── skills/                # Skills (/<name>)
│   ├── explore/
│   ├── no-code-change/
│   ├── propose/
│   └── review/
└── commands/              # Slash commands (/<name> or /<group>:<name>)
    ├── commit.md
    ├── show-plan.md
    ├── fable-design-opus-execute.md
    ├── dev/
    │   ├── development-guideline.md
    │   ├── parallel-development.md
    │   ├── finishing-development.md
    │   ├── ticket.md
    │   ├── 1-design.md
    │   ├── 2-implement.md
    │   ├── 3-review.md
    │   ├── full-dev-cycle.md
    │   ├── learn-conventions.md
    │   ├── code-review.md
    │   ├── security-review.md
    │   ├── simplify.md
    │   ├── full-review.md
    │   ├── investigate.md
    │   ├── create-readme.md
    │   ├── debt.md
    │   └── help.md
    └── hfv/
        ├── full.md
        ├── hypothesis.md
        ├── validate-hypothesis.md
        ├── fix.md
        └── archive.md
```
