---
name: 2-implement
description: "Implement phase: a fresh dev-implementer agent turns an approved plan/<slug>/plan.md into an OpenSpec change, then codes from both under dev:development-guideline (spec-driven, TDD, visual-driven, visual confirmation) until every step is ticked and verified. Replaces typing '/goal write the plan into ./docs/plans, follow it, finish autonomously, /dev:development-guideline'. Triggers on /dev:2-implement, 'implement the plan', 'build it'."
argument-hint: "[plan/<slug>/plan.md | requirement text]"
---

# 2 — Implement

You are the coordinator. The build runs in a fresh `dev-implementer` agent.

## Steps

1. Find the plan from `$ARGUMENTS`:
   - A path to a plan with `Status: approved` → use it.
   - Requirement text, or a plan still in `draft` → run `/dev:1-design` instead (read `~/.claude/commands/dev/1-design.md` and follow it), then stop. The build starts only when the user runs `/dev:2-implement` on the approved plan.
   - Empty → use the only approved plan in `plan/`, or ask in one line.
2. Card: `python3 ~/.claude/scripts/dev/orca-card.py implement`
3. Spawn `dev-implementer` with `plan: <path>`. When the plan's `## Repos` has 2 or more repos, check first if they can build in parallel (below).
4. Read its report.
   - Check the plan with `python3 ~/.claude/scripts/dev/plan-status.py plan/<slug>/plan.md`. Trust its `done` and `left`, not the agent's report.
   - Check the change with `openspec status --change <slug> --json`, run in the repo that holds the plan. No change → the agent wrote code without a spec. Spawn a NEW `dev-implementer` on the same plan, and tell it to write the change before anything else.
   - `done: true` → step 5.
   - `done: false` and the agent did not report a blocker → spawn a NEW `dev-implementer` on the same plan. A fresh agent continues from the ticks. At most 3 rounds, then report `left`.
   - `STATUS: blocked` → tell the user the blocker in one sentence, run `orca-card.py blocked`, and stop.
   - `STATUS: needs-db` → there is no local database for `DB`. Ask the user with AskUserQuestion what to do, never pick for them:
     - clone it from dev (Recommended): `localdb.py clone` reads dev once, then everything runs on the copy
     - load a `.sql`, `.bacpac` or `.dacpac` file they give
     - start empty, from the project's own migrations

     Then spawn a NEW `dev-implementer` with `plan` and `db: <their answer>`, like `db: clone .env.dev1 --prefix OMEGA`.
5. Spawn `dev-convention-learner` with `phase: implement` and `plan`.
6. Tell the user what now works, with the evidence path from `VERIFIED`, the OpenSpec change path from `CHANGE`, and the next step: `/dev:3-review plan/<slug>/plan.md`.

## One implementer per repo

Read only the plan's `## Matrix`. Group the steps by the worktree their `Touches` starts with. No step's `Depends on` names a step in another group → the repos build in parallel:

1. Spawn one `dev-implementer` with `plan` and `only: change`. It writes the OpenSpec change and gets the local database ready. `STATUS: needs-db` → handle it as step 4 says, then spawn it again.
2. Spawn one `dev-implementer` per repo in ONE message, each with `plan` and `repo: <its worktree>`.
3. When all have reported, spawn one more `dev-implementer` with `plan`. Every step is ticked by then, so it goes straight to the plan's `## Verification`. Read its report as step 4 says.

A step that needs another repo's step, like a frontend step that calls the new API → one implementer for the whole plan, as before.

## Local database

The build writes to a local database only; reading dev is fine. The rules are "Database: read dev, write local" in `~/.claude/commands/dev/development-guideline.md`. The toolkit is `uv run ~/.claude/scripts/dev/localdb.py`, run it with no command for its help.

## Cross-References

- Methodology the agent follows → `/dev:development-guideline`
- Next phase → `/dev:3-review`
