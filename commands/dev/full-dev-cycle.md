---
name: full-dev-cycle
description: "Run design → implement → review end to end for one ticket, each phase in a fresh agent, stopping after design and after review for you. Never starts the build until you say go. Moves the Orca card through the board as it goes. Triggers on /dev:full-dev-cycle, 'run the full cycle', 'do this ticket end to end'. Takes a Jira URL/key, a Notion URL, a ticket file, or plain text; with no argument it uses the Jira ticket Orca linked to this worktree."
argument-hint: "[Jira URL/key | Notion URL | plan/<slug>/ticket.md | requirement text]"
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
7. Open every HTML page with `decision-page.py open <page>`, which puts it in a new Orca browser tab. Never `open <page>` yourself; the script falls back to the system browser only outside Orca.
8. When the ticket needs another repo, set up its worktree yourself (below) before the next agent runs. Do not ask the user to make it.
9. Every phase reads dev as it likes and writes to a local database only, the way "Database: read dev, write local" in `/dev:development-guideline` says. When the implementer reports `STATUS: needs-db`, ask the user what to do, the way `/dev:2-implement` says. Never pick for them.

## Other repos

A ticket can need changes in a second repo, like OM.Robot next to Omega. Each extra repo gets its own worktree, and the ticket lists it.

1. Already listed under the ticket's `## Repos` → reuse that worktree.
2. Otherwise make one. Orca first: if `orca worktree current --json` answers, load the guide (`orca skills get orca-cli`) and use it:
   - find the repo: `orca repo list --json`; missing → `orca repo add --path <its clone> --json`
   - reuse a worktree already on the ticket's branch: `orca worktree list --repo id:<repoId> --json`
   - else `orca worktree create --repo id:<repoId> --name <ticket-branch> --parent-worktree active --json`. Leave out `--base-branch`, so it starts from the repo's default base.
   - take `path` and `branch` from the JSON. Later Orca calls name it `path:<abs path>`.
3. No Orca → `git -C <its clone> worktree add <sibling dir> -b <ticket-branch>` from the repo's default base.
4. Add it to the ticket under `## Repos` as a row: repo, worktree path, branch.

Making a new worktree for another repo is allowed. Switching the branch of any existing checkout is not.

## When design is done

1. `python3 ~/.claude/scripts/dev/orca-card.py waiting-decisions`. The card gets the unread dot.
2. Tell the user in two lines: the plan path with the canvas link when the designer reported `CANVAS: <url>`, and the next step by name: "next: `/dev:2-implement plan/<slug>/plan.md` — say go to run it, or tell me what to change".

## When done

1. `python3 ~/.claude/scripts/dev/orca-card.py ready`
2. The ticket has a `Jira: <KEY>` line → post the same three lines to the issue: `orca jira comment add <KEY> --body-file - --json`. Moving the issue's status is the human's call.
3. Tell the user in three lines: what now works with the evidence path, the plan path, and the next step, `/dev:finishing-development`.

## Cross-References

- Tickets on the Orca board → `/dev:ticket`
- Methodology → `/dev:development-guideline`
- Landing → `/dev:finishing-development`
