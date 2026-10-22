---
name: finishing-development
description: "Use when development work is complete and ready to land — archives any active OpenSpec change, then commits, pushes and merges each repo the work touched, following that repo's own landing rules in <repo>/.claude/finishing-development.md. When a repo has no rules file yet, asks the user for its rules first and never lands that repo without them. Takes one optional argument: a target branch, used only to prefill the questions."
---

# Finishing Development

## Overview

The closing ritual for a development session: **archive → land each repo by its own rules**. Run it only once all work is implemented and visually confirmed (see `dev:development-guideline`).

Every repo lands differently: one merges into `dev`, one opens a PR, a wrapper repo only bumps gitlinks. So each repo keeps its landing rules in its own `.claude/finishing-development.md`, and this command follows that file and nothing else.

**Never land a repo without its rules file.** No file means you ask the user, write the file, and get their yes on it before any commit, push or merge in that repo.

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

For each repo, do exactly what its `finishing-development.md` says: commit, push, merge or PR, and the follow-ups. When it says merge, build the merge commit without switching branch: never `git checkout` the target (it is often checked out in another worktree, and switching is forbidden).

```bash
git fetch origin "$TARGET"
TREE=$(git merge-tree --write-tree "origin/$TARGET" HEAD) || { echo "$TREE"; exit 1; }   # conflict → stop
C=$(git commit-tree "$TREE" -p "origin/$TARGET" -p HEAD -m "Merge branch '$CURRENT' into $TARGET")
git push origin "${C}:refs/heads/$TARGET"   # braces: zsh reads $C:r as a modifier
git fetch origin "$TARGET" && git merge-base --is-ancestor HEAD "origin/$TARGET"   # proves it landed
```

A rule the file does not cover → ask the user; never guess.

## Default rules

Offered as the suggested answer in Step 1, never applied without the user's yes.

| Rule | Default |
|---|---|
| Target | the `<target>` argument, else the current branch, else `dev`, else `master` / `main` |
| Commit | `git add -A`, skip when the tree is clean |
| Push | `git push -u origin <current>` |
| Land | merge `--no-ff` into the target when it differs from the current branch, then push it |

## Safety

- Never land a repo whose `.claude/finishing-development.md` is missing or not yet confirmed by the user.
- Never force-push.
- If a merge conflicts, **stop and resolve in this session** with full context; never abandon or force the merge.
- Confirm `git status` is clean and each push succeeded before declaring done, repo by repo.

## Cross-References

- Archiving → `opsx:archive`, `openspec-archive-change`
- Methodology this closes out → `dev:development-guideline`
- Parallel worktree integration that precedes this → `dev:parallel-development`
- End-to-end orchestration → `dev:full-dev-cycle`
