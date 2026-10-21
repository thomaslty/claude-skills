---
name: full-dev-cycle
description: "Run design → implement → review end to end for one ticket, each phase in a fresh agent, stopping after design and after review for you. Never starts the build until you say go. Moves the Orca card through the board as it goes. Triggers on /dev:full-dev-cycle, 'run the full cycle', 'do this ticket end to end'. Takes a Jira URL/key, a Notion URL, a ticket file, or plain text; with no argument it uses the Jira ticket Orca linked to this worktree."
argument-hint: "[Jira URL/key | Notion URL | docs/tickets/<slug>.md | requirement text]"
---

# Full Dev Cycle

You are a thin coordinator. Keep this session small: never read source code or diffs yourself, and pass only paths and the agents' reports between phases. Every phase runs in fresh agents, so one phase's context never leaks into the next.

## The cycle

| Phase | Runs | Then |
|---|---|---|
| 1 Design | `/dev:1-design` | **stop, wait for go** |
| 2 Implement | `/dev:2-implement` | review |
| 3 Review | `/dev:3-review` | **stop, wait for picks** |
| 4 Fix | `dev-implementer` fixes | re-review |
| 5 Re-review | `/dev:3-review` | **stop**, only if new T0 |

Each phase is the command of the same name. Read `~/.claude/commands/dev/<phase>.md` and follow it, passing the plan path along. Convention learning runs at the end of each phase, as those files say.

## Rules

1. **Never start the build by yourself.** After design, always stop, even when the designer asked nothing. Show the plan, then wait. Run phase 2 only when the user says go, like "go", "implement", or "build it", in their own message.
2. **Always stop after review.** The user's picks on the review page are the only go-ahead for fixes.
3. Between those two stops, go on without asking. Stop early only for a blocker.
4. Fix → re-review runs at most 2 rounds. After that, show what is left and stop.
5. Never switch branch, never commit, never push, never merge.
6. Check the plan with `plan-status.py`, and move the card with `orca-card.py`, never by hand.

## When design is done

1. `python3 ~/.claude/scripts/dev/orca-card.py waiting-decisions`. The card gets the unread dot.
2. Tell the user in two lines: the plan path, and "say go to build it, or tell me what to change".

## When done

1. `python3 ~/.claude/scripts/dev/orca-card.py ready`
2. The ticket has a `Jira: <KEY>` line → post the same three lines to the issue: `orca jira comment add <KEY> --body-file - --json`. Moving the issue's status is the human's call.
3. Tell the user in three lines: what now works with the evidence path, the plan path, and the next step, `/dev:finishing-development`.

## Cross-References

- Tickets on the Orca board → `/dev:ticket`
- Methodology → `/dev:development-guideline`
- Landing → `/dev:finishing-development`
