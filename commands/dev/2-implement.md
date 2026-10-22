---
name: 2-implement
description: "Implement phase: a fresh dev-implementer agent follows an approved plan/<slug>/plan.md under dev:development-guideline (TDD, visual-driven, visual confirmation) until every step is ticked and verified. Replaces typing '/goal write the plan into ./docs/plans, follow it, finish autonomously, /dev:development-guideline'. Triggers on /dev:2-implement, 'implement the plan', 'build it'."
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
3. Spawn `dev-implementer` with `plan: <path>`.
4. Read its report.
   - Check the plan with `python3 ~/.claude/scripts/dev/plan-status.py plan/<slug>/plan.md`. Trust its `done` and `left`, not the agent's report.
   - `done: true` → step 5.
   - `done: false` and the agent did not report a blocker → spawn a NEW `dev-implementer` on the same plan. A fresh agent continues from the ticks. At most 3 rounds, then report `left`.
   - `STATUS: blocked` → tell the user the blocker in one sentence, run `orca-card.py blocked`, and stop.
5. Spawn `dev-convention-learner` with `phase: implement` and `plan`.
6. Tell the user what now works, with the evidence path from `VERIFIED`, and the next step: `/dev:3-review plan/<slug>/plan.md`.

## Cross-References

- Methodology the agent follows → `/dev:development-guideline`
- Next phase → `/dev:3-review`
