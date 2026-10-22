---
name: 3-review
description: "Review phase: four fresh dev-reviewer agents run in parallel (correctness, security, feature, completeness) over the diff against the plan, report T0 issues only, and show them on an HTML page where you pick fix / skip per finding and paste the JSON back. Read-only until you paste. Triggers on /dev:3-review, 'review the work', 'review this ticket'."
argument-hint: "[docs/plans/<slug>.md] [--base <ref>]"
---

# 3 — Review

You are the coordinator. Each lens runs in its own fresh `dev-reviewer` agent. Nothing is changed until the user pastes their answers.

## Steps

1. Plan: from `$ARGUMENTS`, or the only plan in `docs/plans/`, or ask in one line.
2. Base: `--base <ref>` if given, otherwise `git merge-base HEAD origin/HEAD` (fall back to `master` or `main`).
3. Card: `python3 ~/.claude/scripts/dev/orca-card.py review`
4. Spawn 4 `dev-reviewer` agents in ONE message, with `lens` set to `correctness`, `security`, `feature`, and `completeness`, plus `plan` and `base`.
5. Save each agent's JSON array verbatim as `docs/reviews/<slug>.<lens>.json`. Do not edit, merge or rewrite them.
6. Build the page from them:

```bash
python3 ~/.claude/scripts/dev/review-page.py --plan docs/plans/<slug>.md docs/reviews/<slug>.{correctness,security,feature,completeness}.json
```

   It merges findings at the same `file:line` into one (listing every lens), writes `docs/reviews/<slug>.findings.json`, and builds `docs/reviews/<slug>.html`.
   - `findings: 0` → tell the user "review clean: 4 lenses, 0 T0 issues", run `orca-card.py ready`, and stop.
7. Open it: `python3 ~/.claude/scripts/dev/decision-page.py open docs/reviews/<slug>.html`. Each finding links to its file on the page, so open no file or diff tabs.
8. Run `orca-card.py waiting-review`. Tell the user, in two lines, the count by lens from step 6, and "pick on the page, then type `done` here (or press Copy and paste the JSON)". Stop and wait.
9. Get the answers: `python3 ~/.claude/scripts/dev/decision-page.py answers docs/reviews/<slug>.html`, or the pasted JSON when it exits with code 3. Then:
   - Spawn `dev-convention-learner` with `phase: review`, `plan`, and `feedback: <the answers>`. Skipped findings and comments are the strongest signal of what this project does not care about.
   - Append a `## Review` section to the plan listing each finding id, its choice, and the comment.
   - If any finding is `fix` or `Other`: run `orca-card.py fixing`, then spawn `dev-implementer` with `plan` and `fixes`: those findings from `docs/reviews/<slug>.findings.json`, plus the user's comments. Your picks on the page are the go-ahead for these fixes.

## Cross-References

- Single-lens deep reviews → `/dev:code-review`, `/dev:security-review`, `/dev:simplify`
- Landing the work → `/dev:finishing-development`
