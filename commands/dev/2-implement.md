---
name: 2-implement
description: "Implement phase: a fresh dev-implementer agent follows an approved docs/plans/<slug>.md under dev:development-guideline (TDD, visual-driven, visual confirmation) until every step is ticked and verified. Replaces typing '/goal write the plan into ./docs/plans, follow it, finish autonomously, /dev:development-guideline'. Triggers on /dev:2-implement, 'implement the plan', 'build it'."
argument-hint: "[docs/plans/<slug>.md | requirement text]"
---

# 2 — Implement

You are the coordinator. The build runs in a fresh `dev-implementer` agent.

## Steps

1. Find the plan from `$ARGUMENTS`:
   - A path to a plan with `Status: approved` → use it.
   - Requirement text, or a plan still in `draft` → run `/dev:1-design` first (read `~/.claude/commands/dev/1-design.md` and follow it), then come back with the approved plan.
   - Empty → use the only approved plan in `docs/plans/`, or ask in one line.
2. Card: `orca worktree set --worktree "path:$ROOT" --workspace-status in-progress --comment "implement" --json` (skip when not an Orca worktree, same check as `/dev:1-design`).
3. Spawn `dev-implementer` with `plan: <path>`.
4. Read its report.
   - `STATUS: done` with every step ticked → step 5.
   - `STATUS: done` but the plan still has `- [ ]` steps → spawn a NEW `dev-implementer` on the same plan. A fresh agent continues from the ticks. At most 3 rounds, then report what is left.
   - `STATUS: blocked` → tell the user the blocker in one sentence, mark the card `blocked` and unread, and stop.
5. Spawn `dev-convention-learner` with `phase: implement` and `plan`.
6. Tell the user what now works, with the evidence path from `VERIFIED`, and the next step: `/dev:3-review docs/plans/<slug>.md`.

## Cross-References

- Methodology the agent follows → `/dev:development-guideline`
- Next phase → `/dev:3-review`
