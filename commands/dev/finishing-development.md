---
name: finishing-development
description: "Use when development work is complete and ready to land — archives any active OpenSpec change, then commits in small batches, pushes and merges each repo the work touched, following that repo's own landing rules in <repo>/.claude/finishing-development.md. Never merges until the user says yes three times, in three separate questions. When a repo has no rules file yet, asks the user for its rules first and never lands that repo without them. Takes one optional argument: a target branch, used only to prefill the questions."
---

# Finishing Development

## Overview

The closing ritual for a development session: **archive → land each repo by its own rules**. Run it only once all work is implemented and visually confirmed (see `dev:development-guideline`).

Every repo lands differently: one merges into `dev`, one opens a PR, a wrapper repo only bumps gitlinks. So each repo keeps its landing rules in its own `.claude/finishing-development.md`, and this command follows that file and nothing else.

**Never land a repo without its rules file.** No file means you ask the user, write the file, and get their yes on it before any commit, push or merge in that repo.

**Never merge without three yeses.** You commit and push on your own. A merge waits until the user has picked `Yes, merge` in three separate questions in this run (Step 3c).

## Step 0 — Find the repos

1. The ticket's or plan's `## Repos` table lists every repo and worktree the work touched. Use it.
2. No table → the current repo, plus each submodule (`git submodule status`) that has changes.
3. Order: other repos and submodules first, the repo holding their gitlinks last, so its gitlink commit points at commits that already exist.

## Step 1 — Load or create each repo's rules

For each repo, read `<repo>/.claude/finishing-development.md`.

- **It exists** → use it as written. Show the user one line per repo: the repo and the rules it will follow.
- **It is missing** → stop and ask the user for this repo's rules, with the questions below. Offer the defaults from "Default rules" as the suggested answer, never apply them on your own. Write their answers to `<repo>/.claude/finishing-development.md` in the format below, show the file, and land that repo only after they confirm it. Ask whether the file itself should be committed in that repo.

Questions, one set per repo that has no file:

| Question | Example answer |
|---|---|
| Target branch | `dev` |
| Commit message style | conventional, `feat(import): …` |
| Push the feature branch? | yes, set upstream |
| Land how? | merge `--no-ff` into target |
| | or open a PR, never merge |
| Push the target after merge? | yes |
| Before landing | run `pytest -m mock_unit` |
| Never | force-push, commit `.env` |
| After landing | bump the gitlink in the wrapper repo |

### File format

```markdown
# Finishing rules — <repo name>

Target branch: dev
Commit message: conventional, like `feat(import): gate data import on DataImport.Modify`
Push feature branch: yes, `git push -u origin <branch>`
Land: merge `--no-ff` into the target, then push the target
Before landing: <checks to run, or "none">
Never: force-push; commit `.env`
After landing: <follow-ups, or "none">
Commit this file: yes | no
```

## Step 2 — Archive active OpenSpec changes (if any)

If there is an active, fully-implemented OpenSpec change, archive it with `opsx:archive` (or `openspec-archive-change`) before committing, so the archive lands in the same commit. No active change → skip.

## Step 3 — Land each repo, in order

For each repo, do exactly what its `finishing-development.md` says: commit, push, merge or PR, and the follow-ups, in the order below. A rule the file does not cover → ask the user; never guess.

### 3a — Commit in small batches

- One commit per logical change, like the migration in one, the endpoint in the next, its tests with it.
- Stage by path with `git add <paths>`, never one `git add -A` for the whole diff.
- Use the message style from the rules file.

### 3b — Push the feature branch

- `git push -u origin <current>` when the rules say push. You do not have to ask for this.

### 3c — Merge gate: ask three times

Merge means anything that puts this branch's commits on the target: `git merge`, a push to `refs/heads/<target>`, `gh pr merge`, or turning on auto-merge. Opening a PR is not a merge.

Check it merges cleanly first, without switching branch: never `git checkout` the target (it is often checked out in another worktree, and switching is forbidden).

```bash
git fetch origin "$TARGET"
TREE=$(git merge-tree --write-tree "origin/$TARGET" HEAD) || { echo "$TREE"; exit 1; }   # conflict → stop
git log --oneline "origin/$TARGET..HEAD"   # what the merge brings in
```

Then ask with `AskUserQuestion`, three separate calls, each sent only after the answer to the one before comes back:

1. `Merge <branch> into <target> in <repo>?`
2. `These <n> commits go to <target>: <git log lines>. Still merge?`
3. `Last ask: push the merge to origin/<target> now?`

- Options are `No, stop here` first and `Yes, merge` second. Mark neither as Recommended.
- Only `Yes, merge` counts. No, Other text, a dismissed question or a denied call → do not merge, stop.
- Never put the three questions in one call, and never count one answer as more than one yes.
- A yes from earlier in the chat, the plan, the rules file, the `<target>` argument, `/dev:full-dev-cycle` or bypass permissions mode is not one of the three.
- Each repo gets its own three asks.
- Something changes after Ask 1, like a new commit or a conflict fix → start again at Ask 1.
- You cannot ask, like when running as a sub-agent → do not merge, stop after the push and tell the user.

### 3d — Merge

Only after three `Yes, merge` answers:

```bash
C=$(git commit-tree "$TREE" -p "origin/$TARGET" -p HEAD -m "Merge branch '$CURRENT' into $TARGET")
git push origin "${C}:refs/heads/$TARGET"   # braces: zsh reads $C:r as a modifier
git fetch origin "$TARGET" && git merge-base --is-ancestor HEAD "origin/$TARGET"   # proves it landed
```

- The push is rejected when `origin/<target>` moved since the check. Never force it: fetch, check again, and start again at Ask 1.
- The user said no → skip the merge and the "After landing" steps, and tell them what was committed and pushed.

## Default rules

Offered as the suggested answer in Step 1, never applied without the user's yes.

| Rule | Default |
|---|---|
| Target | the `<target>` argument, else the current branch, else `dev`, else `master` / `main` |
| Commit | small batches staged by path, skip when the tree is clean |
| Push | `git push -u origin <current>` |
| Land | merge `--no-ff` into the target when it differs from the current branch, after three yeses (Step 3c), then push it |

## Safety

- Never land a repo whose `.claude/finishing-development.md` is missing or not yet confirmed by the user.
- Never merge without three `Yes, merge` answers in this run, per repo (Step 3c). A rules file cannot turn this off.
- Never force-push.
- If a merge conflicts, **stop and resolve in this session** with full context; never abandon or force the merge.
- Confirm `git status` is clean and each push succeeded before declaring done, repo by repo.

## Cross-References

- Archiving → `opsx:archive`, `openspec-archive-change`
- Methodology this closes out → `dev:development-guideline`
- Parallel worktree integration that precedes this → `dev:parallel-development`
- End-to-end orchestration → `dev:full-dev-cycle`
