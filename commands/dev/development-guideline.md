---
name: development-guideline
description: "Use when starting or planning any development work on this project — implementing a feature, enhancement, or bug fix, deciding how to build something, or before claiming work is done. Establishes the mandatory methodology: proposal-driven planning, TDD for backend, visual-driven development for frontend, and non-negotiable visual confirmation of every feature and every bug fix."
---

# Development Guideline

## Overview

The development constitution for this project. Three pillars, no exceptions:

1. **Proposal-driven** — every change starts as an OpenSpec proposal before any code.
2. **Backend = Test-Driven Development (TDD)** — failing test first, then code.
3. **Frontend = Visual-Driven Development (VDD)** — build against the rendered UI, confirm on screen.

**The Iron Rule: you MUST visually confirm every feature works and every bug is fixed in the running app. Visual confirmation is mandatory and is NEVER skipped.**

## When to Use

- Starting any feature, enhancement, or bug fix on this project
- Deciding how to approach an implementation
- Before declaring any feature "done" or any bug "fixed"

Use at the start of development work, and again before claiming completion.

## The Three Pillars

| Phase | Layer | Method | Definition of done |
|---|---|---|---|
| Plan | All | Proposal-driven | Approved proposal exists |
| Build | Backend | TDD | Failing test → code → green |
| Build | Frontend | VDD | UI built, seen on screen |
| Verify | All | Visual confirm | Seen working in real app |

### 1. Proposal-driven planning

No code before a proposal. Use `opsx:propose` (or `openspec-propose`) to create the change and its artifacts (proposal, design, specs, tasks). Implement with `opsx:apply`. If more than one proposal will be created in this session, use `dev:parallel-development`.

### 2. Backend — Test-Driven Development

**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development.

Write the failing test first, watch it fail (RED), write minimal code to pass (GREEN), refactor. No production code without a failing test.

### 3. Frontend — Visual-Driven Development

Build the interface, render it, and iterate against what you actually see — not against assumptions.

**REQUIRED SUB-SKILL:** Use frontend-design for build quality. Drive the real UI with the chrome-devtools or playwright MCP tools and screenshot it.

## The Visual-Confirmation Mandate (non-negotiable)

**Violating the letter of this rule is violating its spirit.** "It compiles", "tests pass", and "the code looks correct" are NOT visual confirmation.

Before any feature is "done" or any bug is "fixed", you MUST:

1. Run the actual app (use the `run` skill / the project run command).
2. Exercise the feature — or reproduce the now-fixed bug path — in the running app.
3. Capture visual evidence: a screenshot of the UI for frontend; the real rendered output/response for backend.
4. Confirm the evidence shows the expected behavior, then say so plainly with the evidence.

For UI: screenshot via chrome-devtools (`take_screenshot`) or playwright (`browser_take_screenshot`). For backend with no UI: exercise the real running endpoint/flow and show the actual response — not just a unit-test assertion.

### Red Flags — STOP, you are about to skip visual confirmation

- "Tests pass, so it works" → tests ≠ seeing it work
- "The change is trivial / obvious" → trivial changes break too
- "I confirmed something similar already" → confirm THIS change
- "No time / I'll confirm later" → later = never; confirm now
- "I can't easily run the UI" → make it runnable; do not skip
- "The diff clearly fixes it" → reproduce the fixed path on screen

**All of these mean: run the app and visually confirm before claiming done.**

### Rationalization table

| Excuse | Reality |
|---|---|
| "Unit tests cover it" | Tests pass while UX breaks |
| "Too small to verify" | Small changes cause regressions |
| "Backend has no UI" | Show real response from running app |
| "Verified in a prior run" | Each change needs its own proof |
| "Confirm before merge later" | Unconfirmed = not done; no merge |

## Cross-References

- Multiple proposals in one session → `dev:parallel-development`
- Proposals / changes → `opsx:propose`, `opsx:apply`
- Backend tests → superpowers:test-driven-development
- Frontend build quality → frontend-design
- Driving / screenshotting the UI → chrome-devtools-mcp:chrome-devtools, playwright
- Running the app / confirming behavior → `run`, `verify`
