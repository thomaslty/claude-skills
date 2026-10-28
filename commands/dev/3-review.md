---
name: 3-review
description: "Review phase: four fresh dev-reviewer agents run in parallel (correctness, security, feature, completeness) over the diff against the plan, report T0 issues only, and show each one right here in the terminal with its root cause, impact and fix. You reply fix / skip per finding in chat. Read-only until you reply. Triggers on /dev:3-review, 'review the work', 'review this ticket'."
argument-hint: "[plan/<slug>/plan.md] [--base <ref>]"
---

# 3 — Review

You are the coordinator. Each lens runs in its own fresh `dev-reviewer` agent. Nothing is changed until the user replies.

Review talks to the user in the terminal only. No HTML page, no JSON to copy.

## Steps

1. Plan: from `$ARGUMENTS`, or the only plan in `plan/`, or ask in one line.
2. Base: `--base <ref>` if given, otherwise `git merge-base HEAD origin/HEAD` (fall back to `master` or `main`).
3. Card: `python3 ~/.claude/scripts/dev/orca-card.py review`
4. Spawn 4 `dev-reviewer` agents in ONE message, with `lens` set to `correctness`, `security`, `feature`, and `completeness`, plus `plan` and `base`.
5. Save each agent's JSON array verbatim as `dev/<slug>/review/<lens>.json`. Do not edit, merge or rewrite them. On a re-review, first move the last round's files into `dev/<slug>/review/round<n>/`.
6. Merge them:

```bash
python3 ~/.claude/scripts/dev/review-findings.py --plan plan/<slug>/plan.md dev/<slug>/review/{correctness,security,feature,completeness}.json
```

   It merges findings at the same `file:line` into one (listing every lens), writes `dev/<slug>/review/findings.json`, and writes `dev/<slug>/review/findings.md` for the terminal.
   - `findings: 0` → tell the user "review clean: 4 lenses, 0 T0 issues", run `orca-card.py ready`, and stop.
7. Print `dev/<slug>/review/findings.md` in the terminal as it is: the count by lens, then every finding with its `Where`, root cause, impact and fix. Never cut it to titles. Open no file or diff tabs; the `Where` path is the link.
8. Run `orca-card.py waiting-review`. End with one line, like: "Reply here, like `fix all` or `sec-1 fix, cor-2 skip: we only log ids`." Stop and wait.
9. The user's reply is the answer. A finding it does not mention → ask about just those, in one line. Then:
   - Spawn `dev-convention-learner` with `phase: review`, `plan`, and `feedback: <the reply verbatim>`. Skipped findings and comments are the strongest signal of what this project does not care about.
   - Append a `## Review` section to the plan listing each finding id, its choice, and the comment.
   - If any finding is to be fixed, or the reply asks for something else: run `orca-card.py fixing`, then spawn `dev-implementer` with `plan` and `fixes`: those findings from `dev/<slug>/review/findings.json`, plus the user's comments. The reply is the go-ahead for these fixes.

## Cross-References

- Single-lens deep reviews → `/dev:code-review`, `/dev:security-review`, `/dev:simplify`
- Landing the work → `/dev:finishing-development`
