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
| 3 Review | `/dev:3-review` | **stop, wait for your reply** |
| 4 Fix | `dev-implementer` per repo | re-review |
| 5 Re-review | `/dev:3-review`, the fix diff only | **stop**, only if new T0 |

Each phase is the command of the same name. Read `~/.claude/commands/dev/<phase>.md` and follow it, passing the plan path along. Skip each phase file's `dev-convention-learner` step: inside the cycle the learner runs once, in `## When done`. On the offload test, one after each phase blocked the next one 3 times for 1 to 2 minutes each.

## Rules

1. **Never start the build by yourself.** After design, always stop, even when the designer asked nothing. Show the plan, then wait. Run phase 2 only when the user says go, like "go", "implement", or "build it", in their own message.
2. **Always stop after review.** The user's reply to the findings is the only go-ahead for fixes.
   - A `/goal`, a hook or your own plan never answers a stop. Pass one only when the user's own message names it, like a plan step they approved that says to run this cycle through review. Never write a reply in the user's name: no "fix all" you made up, and no `feedback:` for the learner that the user did not type. On the offload test, a made-up "fix all" became 3 rules marked `human` in `.claude/conventions.md`.
3. Between those two stops, go on without asking. Stop early only for a blocker.
4. Fix → re-review runs once. The re-review reads only what the fixes changed, the way `/dev:3-review` says. Then show what is left and stop; another round starts only when the user asks for it. On the offload test, round 2 re-read all 21 files to check 2 fixes, and both bugs it found were in the fixed lines.
5. Never switch branch, never commit, never push, never merge.
6. Check the plan with `plan-status.py`, and move the card with `orca-card.py`, never by hand.
7. Explore, design and review talk in the terminal: print the plan, the questions and the findings there, and take the user's reply as the answer. Never build or open an HTML page for them.
8. When the ticket needs another repo, set up its worktree yourself (below) before the next agent runs. Do not ask the user to make it.
9. Every phase reads dev as it likes and writes to a local database only, the way "Database: read dev, write local" in `/dev:development-guideline` says. When the implementer reports `STATUS: needs-db`, ask the user what to do, the way `/dev:2-implement` says. Never pick for them.
10. Two repos never build one after the other. The build and every fix round run one implementer per repo at the same time, the way `/dev:2-implement` says.
11. Every agent you start gets its effort from `## Effort` below.

## Effort

Every agent the dev suite starts gets its effort from this table, as the Agent tool's `effort`. `/dev:1-design`, `/dev:2-implement`, `/dev:3-review` and `/dev:parallel-development` use it too, also outside the cycle. Without it every agent runs at `settings.json`'s `xhigh`: on the offload test that made 60 to 73% of each agent's output hidden thinking, and xhigh still let two real bugs through to review. Never change `settings.json`.

| Agent | Effort | xhigh instead when |
|---|---|---|
| `dev-researcher` | medium | — |
| `dev-designer`, small ticket | medium | — |
| `dev-designer` | high | risky or cross-repo |
| `dev-implementer` | high | its steps are `Risk: high` |
| `dev-implementer`, fixes | high | a fix to a fix |
| `dev-reviewer`, `lens: all` | high | — |
| `dev-reviewer`, `security` | xhigh | always |
| `dev-convention-learner` | low | — |
| qwen, through omp | xhigh | always |

- Risky, for the designer, is decided before the plan exists: the ticket's text names a file or pattern on `.claude/risky.md`, or its `## Repos` lists 2 or more repos.
- A fix to a fix: the finding is in code a fix round already changed, like the round-2 slow drip in the 5-second timeout that round 1 added.
- Inside one ticket, effort only goes up, never down. A designer that reports `SIZE: full` is started again at high.

## Risk

`<repo>/.claude/risky.md` is the repo's list of what is risky: paths and code patterns where a miss breaks other users, like a tenant cache key or a permission check. Every phase reads it:

| Reads it | For |
|---|---|
| `/dev:1-design` | the small path, the designer's effort |
| `dev-designer` | the Matrix's `Risk` column |
| `/dev:2-implement` | the risk split |
| `/dev:3-review` | the security pass |
| `/dev:offload-to-localLLM` | Claude's deep pass |

No file yet → the designer drafts it, the way `## Risk file` in `~/.claude/agents/dev-designer.md` says, and design prints it at its stop. The user's go on the plan is the go on the file; a change they ask for goes in before the build.

## Other repos

A ticket can need changes in a second repo, like OM.Robot next to Omega. Each extra repo gets its own worktree, and the ticket lists it.

1. Already listed under the ticket's `## Repos` → reuse that worktree.
2. Otherwise make one. Orca first: if `orca worktree current --json` answers, load the guide (`orca skills get orca-cli`) and use it:
   - find the repo: `orca repo list --json`; missing → `orca repo add --path <its clone> --json`
   - reuse a worktree already on the ticket's branch: `orca worktree list --repo id:<repoId> --json`
   - else `orca worktree create --repo id:<repoId> --name <ticket-branch> --parent-worktree active --json`. Pass `--base-branch` with the base the user names, usually `origin/dev`: ask for it, since a repo with no base set in Orca starts from a stale default, like Omega.Entity `master` 28 commits behind `dev`.
   - take `path` and `branch` from the JSON. Later Orca calls name it `path:<abs path>`.
3. No Orca → `git -C <its clone> worktree add <sibling dir> -b <ticket-branch>` from the repo's default base.
4. Add it to the ticket under `## Repos` as a row: repo, worktree path, branch.

Making a new worktree for another repo is allowed. Switching the branch of any existing checkout is not.

## When design is done

1. `python3 ~/.claude/scripts/dev/orca-card.py waiting-decisions`. The card gets the unread dot.
2. Tell the user in two lines: the plan path with the canvas link when the designer reported `CANVAS: <url>`, and the next step by name: "next: `/dev:2-implement plan/<slug>/plan.md` — say go to run it, or tell me what to change".

## When done

1. `python3 ~/.claude/scripts/dev/orca-card.py ready`
2. Spawn one `dev-convention-learner` in the background, at `effort: low`, with `phase: cycle`, `plan`, and `feedback:` every reply the user typed in this cycle, verbatim. Do not wait for it.
3. The ticket has a `Jira: <KEY>` line → post the same three lines to the issue: `orca jira comment add <KEY> --body-file - --json`. Moving the issue's status is the human's call.
4. Tell the user in three lines: what now works with the evidence path, the plan path, and the next step, `/dev:finishing-development`.

## Cross-References

- Tickets on the Orca board → `/dev:ticket`
- Methodology → `/dev:development-guideline`
- Landing → `/dev:finishing-development`
