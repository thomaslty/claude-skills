---
description: "Split-brain workflow: Fable 5 designs in the main session, Claude sub-agents execute the code. Use when you want Fable's planning with Claude's implementation. Triggers on /fable-design-claude-execute, 'fable designs claude executes', 'plan with fable build with claude'."
argument-hint: "[task description] [--parallel]"
---

# Fable Designs, Claude Executes

## Overview

Two models, two jobs. The main session (**Fable 5**) owns thinking: explore, decide, write the plan. Sub-agents (**Claude**) own typing: edit files, run tests, report back. Fable never writes production code; Claude never re-decides the design.

**Core principle:** the design must survive the handover in writing. A non-fork sub-agent starts with an EMPTY context — it sees only the prompt you give it. Anything Fable worked out and did not write down is lost.

## Arguments

| Arg | Effect |
|---|---|
| bare text | The task to design + execute |
| `--parallel` | Fan out independent chunks |

The executor is **always Opus**. There is no downgrade flag — never substitute Sonnet or Haiku, however mechanical the task looks.

## Phase 0 — Preflight

1. Confirm the main session model is Fable 5. If it is not, say so in one line and tell the user to run `/model fable`, then stop. Do not silently proceed on another model.
2. If no task was given in `$ARGUMENTS`, ask for it in one line and stop.

## Phase 1 — Design (Fable, main session)

Read-only. Zero edits in this phase.

1. Explore the relevant code — Read / Grep / Glob, and the `Explore` agent for broad sweeps.
2. If the project has `dev:development-guideline`, follow it: proposal-driven, TDD for backend, visual-driven for frontend.
3. Decide the approach. Where two approaches are live, pick one and state why in one line.
4. Write the handover brief (Phase 2) to disk.
5. Show the user a short plan summary (numbered steps, ≤5) and the brief path. **Wait for approval before Phase 3.**

## Phase 2 — The handover brief

Write it to the session scratchpad directory as `handover-<slug>.md`. If no scratchpad path is available, use `./.claude/handover/<slug>.md`.

A brief is complete only if a fresh engineer with no memory of this conversation could execute it. Required sections:

| Section | Contents |
|---|---|
| Goal | What "done" means |
| Files | Exact paths to touch |
| Steps | Ordered, one action each |
| Anchors | `file:line` for each edit |
| Conventions | Patterns to copy |
| Verify | Commands to run |
| Out of scope | What NOT to change |

Never write "as we discussed", "the approach above", or "the usual pattern" — the executor was not there.

## Phase 3 — Execute (Claude sub-agents)

Dispatch with the Agent tool:

- `subagent_type: "general-purpose"` — **never `"fork"`**; fork ignores the model override and would run Fable again.
- `model: "opus"` — always, no exceptions.
- `prompt`: the absolute brief path + an instruction to read it first, plus the hard rules below.

Rules to hand every executor:

1. Read the brief before touching anything.
2. Implement exactly the brief — no scope beyond it.
3. Run the Verify commands; paste real output, never a summary of output.
4. If the brief is wrong or blocked, STOP and report — do not improvise a new design.
5. Report: files changed, verify output, anything skipped.

With `--parallel`: split into chunks that share no files, dispatch all in ONE message. If chunks would touch the same file, go sequential instead. For worktree-level isolation, use `dev:parallel-development`.

## Phase 4 — Verify (Fable, main session)

1. `git diff` the result yourself. Do not trust the executor's self-report.
2. Check each brief step actually landed.
3. Re-run the Verify commands.
4. On a gap: patch the brief and re-dispatch — do not hand-fix silently.
5. Report to the user: what now works, what was skipped, one concrete next action.

## Quick Reference

| Step | Model | Owner | Output |
|---|---|---|---|
| Explore | Fable | Main | Understanding |
| Decide | Fable | Main | Approach |
| Brief | Fable | Main | Brief file |
| Approve | — | User | Go / no-go |
| Implement | Opus | Sub-agent | Code + tests |
| Verify | Fable | Main | Diff review |

## Hard Rules

| Rule | Why |
|---|---|
| Fable writes no prod code | Executor's job |
| Claude re-designs nothing | Designer's job |
| Never `subagent_type: fork` | Drops model override |
| Executor is always Opus | No downgrades |
| Brief is self-contained | Sub-agent has no context |
| Approval gate before dispatch | Cheap to fix a plan |
| Main session verifies diff | Self-reports drift |
