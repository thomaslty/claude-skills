---
name: 2-implement
description: "Implement phase: fresh dev-implementer agents, one per repo at the same time when the plan spans repos like frontend and backend, turn an approved plan/<slug>/plan.md into an OpenSpec change, then code from both under dev:development-guideline (spec-driven, TDD, visual-driven, visual confirmation) until every step is ticked and verified. Replaces typing '/goal write the plan into ./docs/plans, follow it, finish autonomously, /dev:development-guideline'. Triggers on /dev:2-implement, 'implement the plan', 'build it'."
argument-hint: "[plan/<slug>/plan.md | requirement text]"
---

# 2 — Implement

You are the coordinator. The build runs in fresh `dev-implementer` agents. Two repos never build one after the other: a plan that spans repos, like frontend and backend, gets one implementer per repo at the same time.

## Steps

1. Find the plan from `$ARGUMENTS`:
   - A path to a plan with `Status: approved` → use it.
   - Requirement text, or a plan still in `draft` → run `/dev:1-design` instead (read `~/.claude/commands/dev/1-design.md` and follow it), then stop. The build starts only when the user runs `/dev:2-implement` on the approved plan.
   - Empty → use the only approved plan in `plan/`, or ask in one line.
2. Card: `python3 ~/.claude/scripts/dev/orca-card.py implement`
3. Spawn the build:
   - The plan's `## Repos` lists 2 or more repos that change → one implementer per repo (below). Always, with no check first.
   - One repo → spawn `dev-implementer` with `plan: <path>`.
4. Read its report.
   - Check the plan with `python3 ~/.claude/scripts/dev/plan-status.py plan/<slug>/plan.md`. Trust its `done` and `left`, not the agent's report.
   - Check the change with `openspec status --change <slug> --json`, run in the repo that holds the plan. No change → the agent wrote code without a spec. Spawn a NEW `dev-implementer` on the same plan, and tell it to write the change before anything else.
   - `done: true` → step 5.
   - `done: false` and the agent did not report a blocker → spawn a NEW `dev-implementer` on the same plan. A fresh agent continues from the ticks. At most 3 rounds, then report `left`. In a split build this is per repo, as below.
   - `STATUS: blocked` → tell the user the blocker in one sentence, run `orca-card.py blocked`, and stop.
   - `STATUS: needs-db` → there is no local database for `DB`. Ask the user with AskUserQuestion what to do, never pick for them:
     - clone it from dev (Recommended): `localdb.py clone` reads dev once, then everything runs on the copy
     - load a `.sql`, `.bacpac` or `.dacpac` file they give
     - start empty, from the project's own migrations

     Then spawn a NEW `dev-implementer` with `plan` and `db: <their answer>`, like `db: clone .env.dev1 --prefix OMEGA`.
5. Spawn `dev-convention-learner` with `phase: implement` and `plan`.
6. Tell the user what now works, with the evidence path from `VERIFIED`, the OpenSpec change path from `CHANGE`, and the next step: `/dev:3-review plan/<slug>/plan.md`.

## One implementer per repo

A frontend step that calls a new endpoint codes against the plan's `## Contract`, so it never waits for the backend. The Matrix's `Repo` column says which implementer does each step: a repo name like `backend`, `setup` before the split, or `join` after it.

1. Setup: spawn one `dev-implementer` with `plan` and `only: change`. It writes the OpenSpec change, gets the local database ready, does the `setup` steps, and puts an older plan in this shape: the `Repo` column, `## Contract`, and no `Depends on` across repos. `STATUS: needs-db` → handle it as step 4 says, then spawn it again.
2. Split: spawn one `dev-implementer` per repo that has steps in `Repo`, all in ONE message, each with `plan` and `repo: <name>`, like `repo: backend`.
3. One comes back with steps left and no blocker → spawn a NEW one for that repo straight away. Do not wait for the others. At most 3 rounds per repo.
4. Join: when every repo is done, spawn one `dev-implementer` with `plan` and `only: join`. It rebuilds the whole stack, does the `join` steps against the real backend, then the plan's `## Verification`. Read its report as step 4 says.

Never fall back to one implementer for a plan that spans repos. A `Depends on` across repos is the setup implementer's to fix, not a reason to wait.

## Fixes

Review fixes split the same way. Each finding's `where` starts with its repo, like `backend/apis/poc/service/explorer/crypto_rows.py:43`.

- Findings in 2 or more repos → setup with `plan`, `fixes` and `only: change`, which adds each fix as a step with its `Repo`. Then one `dev-implementer` per repo with `plan`, `fixes` and `repo`, in ONE message. Then join with `only: join`.
- Findings in one repo → one `dev-implementer` with `plan` and `fixes`.

## Local database

The build writes to a local database only; reading dev is fine. The rules are "Database: read dev, write local" in `~/.claude/commands/dev/development-guideline.md`. The toolkit is `uv run ~/.claude/scripts/dev/localdb.py`, run it with no command for its help.

## Cross-References

- Methodology the agent follows → `/dev:development-guideline`
- Next phase → `/dev:3-review`
