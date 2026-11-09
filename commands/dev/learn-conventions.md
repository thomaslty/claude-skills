---
name: learn-conventions
description: "Learn this project's coding style and conventions from the latest change and your corrections, and file them into .claude/rules/, each file scoped with paths so it loads only where it applies. Runs automatically at the end of every dev: phase; run it by hand after a session where you corrected Claude. Triggers on /dev:learn-conventions, 'remember this convention', 'learn my style'."
argument-hint: "[what you want remembered]"
---

# Learn Conventions

Read `~/.claude/agents/dev-convention-learner.md` and follow it yourself, in this session, with:

- `phase: manual`
- `plan`: the plan in `plan/` this work belongs to, if there is one
- `feedback`: `$ARGUMENTS`, plus every correction the user typed in this session, verbatim

Show its one-line report to the user.
