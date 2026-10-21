---
name: full-dev-cycle
description: "Run design → implement → review end to end for one ticket, each phase in a fresh agent, stopping only for the decisions only you can make. Moves the Orca card through the board as it goes. Triggers on /dev:full-dev-cycle, 'run the full cycle', 'do this ticket end to end'. Launched for you by /dev:ticket start."
argument-hint: "<docs/tickets/<slug>.md | requirement text>"
---

# Full Dev Cycle

You are a thin coordinator. Keep this session small: never read source code or diffs yourself, and pass only paths and the agents' reports between phases. Every phase runs in fresh agents, so one phase's context never leaks into the next.

## The cycle

| Phase | Runs | Card | Human stop |
|---|---|---|---|
| 1 Design | `/dev:1-design` | in-progress · design | only if decisions |
| 2 Implement | `/dev:2-implement` | in-progress · implement | only if blocked |
| 3 Review | `/dev:3-review` | in-review · review | always: review page |
| 4 Fix | `dev-implementer` fixes | in-progress · fixing | none |
| 5 Re-review | `/dev:3-review` | in-review · review | only if new T0 |

Each phase is the command of the same name. Read `~/.claude/commands/dev/<phase>.md` and follow it, passing the plan path along. Convention learning runs at the end of each phase, as those files say.

## Rules

1. Go from one phase to the next without asking. Stop only at the human stops in the table.
2. Fix → re-review runs at most 2 rounds. After that, show what is left and stop.
3. Never switch branch, never commit, never push, never merge.

## When done

1. Card: `orca worktree set --worktree "path:$ROOT" --workspace-status in-review --comment "ready to land" --unread --json` (skip when not an Orca worktree).
2. The ticket has a `Jira: <KEY>` line → post the same three lines to the issue: `orca jira comment add <KEY> --body-file - --json`. Moving the issue's status is the human's call.
3. Tell the user in three lines: what now works with the evidence path, the plan path, and the next step, `/dev:finishing-development`.

## Cross-References

- Tickets on the Orca board → `/dev:ticket`
- Methodology → `/dev:development-guideline`
- Landing → `/dev:finishing-development`
