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
3. Card: `orca worktree set --worktree "path:$ROOT" --workspace-status in-review --comment "review" --json` (skip when not an Orca worktree).
4. Spawn 4 `dev-reviewer` agents in ONE message, with `lens` set to `correctness`, `security`, `feature`, and `completeness`, plus `plan` and `base`.
5. Merge the 4 arrays. When two findings point at the same `where` and the same problem, keep one and list both lenses.
6. No findings → tell the user "review clean: 4 lenses, 0 T0 issues", run step 9, and stop.
7. Build the review page. Write `docs/reviews/<slug>.json` with one root node per finding:

```json
{
  "title": "Login with magic link — review",
  "kind": "review",
  "ticket": "docs/tickets/login-magic-link.md",
  "plan": "docs/plans/login-magic-link.md",
  "summary": [
    {"type": "table", "head": ["Lens", "T0"], "rows": [["correctness", "1"], ["security", "2"], ["feature", "0"], ["completeness", "0"]]}
  ],
  "roots": ["sec-1"],
  "nodes": {
    "sec-1": {
      "title": "Magic link token logged in plain text",
      "severity": "T0",
      "where": "src/auth/magic.ts:58",
      "context": [
        {"type": "table", "head": ["Lens", "Where"], "rows": [["security", "src/auth/magic.ts:58"]]},
        {"type": "bullets", "items": ["what: <scenario, one line>", "fix: <fix, one line>"]}
      ],
      "options": [
        {"id": "fix", "label": "Fix it", "result": "implementer applies the fix", "recommended": true},
        {"id": "skip", "label": "Skip", "result": "kept as is, noted in the plan"}
      ]
    }
  }
}
```

   No prose: `summary` and `context` are block lists (`table`, `graph`, `bullets`, one-line `text`), same rules as the design page in `~/.claude/agents/dev-designer.md`. A `graph` of the broken call path beats a sentence about it.

   Then run `python3 ~/.claude/templates/dev/build-page.py docs/reviews/<slug>.json docs/reviews/<slug>.html`, and open the page the same way `/dev:1-design` does. Also open the changed files as diff tabs, so each finding can be checked against the code without leaving Orca: `orca file open-changed --worktree "path:$ROOT" --mode diff --json`.
8. Tell the user, in two lines, the finding count by lens, and "pick on the page, then type `done` here (or press Copy and paste the JSON)". Mark the card `waiting: review` and unread. Stop and wait.
9. Get the answers the same way `/dev:1-design` does (`orca eval` on the page, or the pasted JSON), then:
   - Spawn `dev-convention-learner` with `phase: review`, `plan`, and `feedback: <the JSON>`. Skipped findings and comments are the strongest signal of what this project does not care about.
   - If any finding is `fix` or `Other`, spawn `dev-implementer` with `plan` and `fixes: <those findings plus the user's comments>`.
   - Append a `## Review` section to the plan listing each finding id, its choice, and the comment.

## Cross-References

- Single-lens deep reviews → `/dev:code-review`, `/dev:security-review`, `/dev:simplify`
- Landing the work → `/dev:finishing-development`
