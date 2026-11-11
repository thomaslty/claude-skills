---
name: 2-implement
description: "Implement phase: this session, repo by repo when the plan spans repos like frontend and backend, turns an approved plan/<slug>/plan.md into an OpenSpec change, then code from both under dev:development-guideline (spec-driven, TDD, visual-driven, visual confirmation) until every step is ticked and verified. Replaces typing '/goal write the plan into ./docs/plans, follow it, finish autonomously, /dev:development-guideline'. Triggers on /dev:2-implement, 'implement the plan', 'build it'."
argument-hint: "[plan/<slug>/plan.md | requirement text]"
---

# 2 — Implement

You build in this session: read `~/.claude/agents/dev-implementer.md` and follow it yourself, every repo, one after the other. No agent for the build: only the research topics and `/dev:3-review` start agents (Thomas, 2026-11-09: "the explorer, the designer, the implementor, all run in main session, no more subagent. only review is using subagent since it needs clean context", then "the reasearch (explore) agent can sill be subagent driven, since it speeds up the findings / but design, implement MUST stay in main session"). A plan with `Offload: local` is built the same way, with qwen writing the code.

## Steps

1. Find the plan from `$ARGUMENTS`:
   - A path to a plan with `Status: approved` → use it.
   - Requirement text, or a plan still in `draft` → run `/dev:1-design` instead (read `~/.claude/commands/dev/1-design.md` and follow it), then stop. The build starts only when the user runs `/dev:2-implement` on the approved plan.
   - Empty → use the only approved plan in `plan/`, or ask in one line.
2. Card: `python3 ~/.claude/scripts/dev/orca-card.py implement`
3. Start the build:
   - The plan has no `Base:` line → add `Base: <git rev-parse HEAD>` under its `Ticket:` line first, or `Base: 4b825dc642cb6eb9a060e54bf8d69288fbee4904` (git's empty tree) in a repo with no commit yet. You commit as you build, so `/dev:3-review` diffs from here: on a branch with no remote, "the merge base with `master`" is the last build commit and the diff comes out empty.
   - `/dev:offload-to-localLLM` was asked for in this session and the plan has no `Offload:` line → add `Offload: local` under its `Ticket:` line first.
   - The plan has `Offload: local` → build it the way `## With another /dev skill` in `~/.claude/commands/dev/offload-to-localLLM.md` says.
   - The plan's `## Repos` lists 2 or more repos that change → build them in the order `## Every repo` below says.
   - One repo → build it with `plan: <path>`.
   - A step adds a backend test file and the repo has the `omega:add-backend-test` skill, like `backend/.claude/commands/omega/add-backend-test.md` in Omega.Next.AIO → start that file with `/omega:add-backend-test <source file>`, so it lands in the right folder with its wiring. The skill is not there, like in any repo that is not Omega → skip this line and write the test the way the repo's own `CLAUDE.md` says.
4. Check your work.
   - Check the plan with `python3 ~/.claude/scripts/dev/plan-status.py plan/<slug>/plan.md`. Trust its `done` and `left`.
   - Check the change with `openspec status --change <slug> --json`, run in the repo that holds the plan. No change → code was written without a spec. Write the change now, before any more code. A plan with `Size: small` has no change on purpose: skip this check.
   - `done: true` → step 5.
   - `done: false` and no blocker → keep building from the first unticked step.
   - A real blocker → tell the user the blocker in one sentence, run `orca-card.py blocked`, and stop.
   - No local database for the plan → ask the user with AskUserQuestion what to do, never pick for them:
     - clone it from dev (Recommended): `localdb.py clone` reads dev once, then everything runs on the copy
     - load a `.sql`, `.bacpac` or `.dacpac` file they give
     - start empty, from the project's own migrations

     Then do what they picked, with the `localdb.py` command for it, like `clone .env.dev1 --prefix OMEGA`.
5. Learn the conventions: read `~/.claude/agents/dev-convention-learner.md` and follow it with `phase: implement` and `plan`. Inside `/dev:full-dev-cycle`, skip this step: the cycle learns once at the end.
6. Tell the user what now works, with the evidence path, the OpenSpec change path from `CHANGE` when there is one, and the next step: `/dev:3-review plan/<slug>/plan.md`.

## Every repo

You build the repos one after the other, in this order, each the way `dev-implementer.md` says for its mode:

1. `only: change`: write the OpenSpec change, get the local database ready, do the `setup` steps, and put the plan in its shape: the `Repo` column, `## Contract`, and no `Depends on` across repos.
2. `repo: <name>` for each repo with steps in `Repo`, in the Matrix's order. A frontend step that calls a new endpoint codes against the plan's `## Contract`, so the backend's order never holds it up.
3. `only: join`: rebuild the whole stack, do the `join` steps against the real backend, then the plan's `## Verification`.

A step marked `Risk: high` gets no agent of its own: build it yourself with the care its Detail asks for, and `/dev:3-review` adds its security pass.

## Fixes

Review fixes split the same way. Each finding's `where` starts with its repo, like `backend/apis/poc/service/explorer/crypto_rows.py:43`.

You fix them yourself, in this session, the way `## Fix mode` in `dev-implementer.md` says:

- Findings in 2 or more repos → add each fix as a step with its `Repo` (`only: change` with `fixes`), fix each repo in turn (`repo` with `fixes`), then `only: join`.
- Findings in one repo → `fixes` alone.
- The plan has `Offload: local` → the way `## With another /dev skill` in `offload-to-localLLM.md` says.

## Local database

The build writes to a local database only; reading dev is fine. The rules are "Database: read dev, write local" in `~/.claude/commands/dev/development-guideline.md`. The toolkit is `uv run ~/.claude/scripts/dev/localdb.py`, run it with no command for its help.

## Cross-References

- Methodology the agent follows → `/dev:development-guideline`
- Next phase → `/dev:3-review`
