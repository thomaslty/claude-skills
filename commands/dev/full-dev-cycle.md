---
name: full-dev-cycle
description: "Run design → implement → review end to end for one ticket, every phase in this session and only review's reviewers as agents, stopping after design and after review for you. Never starts the build until you say go. Moves the Orca card through the board as it goes. Triggers on /dev:full-dev-cycle, 'run the full cycle', 'do this ticket end to end'. Takes a Jira URL/key, a Notion URL, a ticket file, or plain text; with no argument it uses the Jira ticket Orca linked to this worktree."
argument-hint: "[Jira URL/key | Notion URL | plan/<slug>/ticket.md | requirement text]"
---

# Full Dev Cycle

You run every phase yourself, in this session: explore, design, implement and fix. Only the research topics (`dev-researcher`, in parallel, because it finds things faster) and review start agents; a reviewer needs a clean context that did not write the code. Thomas, 2026-11-09: "the explorer, the designer, the implementor, all run in main session, no more subagent. only review is using subagent since it needs clean context", then "the reasearch (explore) agent can sill be subagent driven, since it speeds up the findings / but design, implement MUST stay in main session". Why: a join implementer ran `make local-db sync WITH_EV=1` on a working local database because its brief offered it, and the session the user talks to only found out when the user's `make up` crashed.

## The cycle

| Phase | Runs | Then |
|---|---|---|
| 1 Design | `/dev:1-design` | **stop, wait for go** |
| 2 Implement | `/dev:2-implement` | review |
| 3 Review | `/dev:3-review` | **stop, wait for your reply** |
| 4 Fix | you, every repo | re-review |
| 5 Re-review | `/dev:3-review`, the fix diff only | **stop**, only if new T0 |

Each phase is the command of the same name. Read `~/.claude/commands/dev/<phase>.md` and follow it, with the plan path. Skip each phase file's convention step: inside the cycle you learn the conventions once, in `## When done`.

## Rules

1. **Never start the build by yourself.** After design, always stop, even when the designer asked nothing. Show the plan, then wait. Run phase 2 only when the user says go, like "go", "implement", or "build it", in their own message.
2. **Always stop after review.** The user's reply to the findings is the only go-ahead for fixes.
   - A `/goal`, a hook or your own plan never answers a stop. Pass one only when the user's own message names it, like a plan step they approved that says to run this cycle through review. Never write a reply in the user's name: no "fix all" you made up, and no `feedback:` for the learner that the user did not type. On the offload test, a made-up "fix all" became 3 rules marked `human` in `.claude/conventions.md`.
3. Between those two stops, go on without asking. Stop early only for a blocker.
4. Fix → re-review runs once. The re-review reads only what the fixes changed, the way `/dev:3-review` says. Then show what is left and stop; another round starts only when the user asks for it. On the offload test, round 2 re-read all 21 files to check 2 fixes, and both bugs it found were in the fixed lines.
5. Never switch branch, never merge. You commit in small batches and push your own feature branch as you build; never ask the user about commits or pushes (Thomas's standing rule, 2026-11-05).
6. Check the plan with `plan-status.py`, and move the card with `orca-card.py`, never by hand.
7. Explore, design and review talk in the terminal: print the plan, the questions and the findings there, and take the user's reply as the answer. Never build or open an HTML page for them.
8. When the ticket needs another repo, set up its worktree yourself (below) before the next phase. Do not ask the user to make it.
9. Every phase reads dev as it likes and writes to a local database only, the way "Database: read dev, write local" in `/dev:development-guideline` says. When there is no local database, ask the user what to do, the way `/dev:2-implement` says. Never pick for them.
10. You build every repo yourself, one after the other in the Matrix's order, and fix them the same way, the way `/dev:2-implement` says. With `Offload: local`, their qwen runs still go at once.
11. The researchers and reviewers get their effort from `## Effort` below. Nothing else starts an agent.

## Effort

Research and review are the only steps that start agents, and each gets its effort here, as the Agent tool's `effort`. Without it every agent runs at `settings.json`'s `xhigh`. Never change `settings.json`.

| Agent | Effort |
|---|---|
| `dev-researcher` | medium |
| `dev-reviewer`, `lens: all` | high |
| `dev-reviewer`, `security` | xhigh |
| qwen, through omp | xhigh |

## Risk

`<repo>/.claude/risky.md` is the repo's list of what is risky: paths and code patterns where a miss breaks other users, like a tenant cache key or a permission check. Every phase reads it:

| Reads it | For |
|---|---|
| `/dev:1-design` | the small path |
| design | the Matrix's `Risk` column |
| `/dev:3-review` | the security pass |
| `/dev:offload-to-localLLM` | Claude's deep pass |

No file yet → you draft it in design, the way `## Risk file` in `~/.claude/agents/dev-designer.md` says, and design prints it at its stop. The user's go on the plan is the go on the file; a change they ask for goes in before the build.

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
2. Tell the user in two lines: the plan path with the canvas link when the plan has a `Canvas:` line, and the next step by name: "next: `/dev:2-implement plan/<slug>/plan.md` — say go to run it, or tell me what to change".

## When done

1. `python3 ~/.claude/scripts/dev/orca-card.py ready`
2. Learn the conventions yourself: read `~/.claude/agents/dev-convention-learner.md` and follow it, with `phase: cycle`, `plan`, and `feedback:` every reply the user typed in this cycle, verbatim.
3. The ticket has a `Jira: <KEY>` line → post the same three lines to the issue: `orca jira comment add <KEY> --body-file - --json`. Moving the issue's status is the human's call.
4. Tell the user in three lines: what now works with the evidence path, the plan path, and the next step, `/dev:finishing-development`.

## Cross-References

- Tickets on the Orca board → `/dev:ticket`
- Methodology → `/dev:development-guideline`
- Landing → `/dev:finishing-development`
