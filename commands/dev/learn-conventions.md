---
name: learn-conventions
description: "Learn this project's coding style and conventions from the latest change and your corrections, and merge them into .claude/conventions.md (imported from CLAUDE.md so every session follows them). Runs automatically at the end of every dev: phase; run it by hand after a session where you corrected Claude. Triggers on /dev:learn-conventions, 'remember this convention', 'learn my style'."
argument-hint: "[what you want remembered]"
---

# Learn Conventions

Spawn `dev-convention-learner` with:

- `phase: manual`
- `plan`: the plan in `plan/` this work belongs to, if there is one
- `feedback`: `$ARGUMENTS`, plus every correction the user typed in this session, verbatim

Show its one-line report.
