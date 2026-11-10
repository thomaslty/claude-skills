---
name: finishing-development
description: "Use when development work is complete and ready to land — archives any active OpenSpec change, then commits in small batches and pushes each repo the work touched, following that repo's own rules in <repo>/.claude/finishing-development.md, then asks the user per repo to pick one of three: open a PR into dev, just push, or stop here, then stops what the session left running (dev:cleanup). Never merges. When a repo has no rules file yet, asks the user for its rules first and never lands that repo without them. Takes one optional argument: a target branch, used only to prefill the questions."
---

# Finishing Development

## Overview

The closing ritual for a development session: **archive → commit and push each repo by its own rules → ask how it lands → clean up what the session left running**. Run it only once all work is implemented and visually confirmed (see `dev:development-guideline`).

Every repo commits and pushes its own way, so each repo keeps its rules in its own `.claude/finishing-development.md`, and this command follows that file for committing and pushing.

**Never merge. Not with any number of yeses.** You commit and push on your own. Landing stops at a pull request at most: per repo, the user picks one of three in Step 3c, and none of the three merges (Thomas, 2026-11-10: "no merge, fix the skill, no merge allowed. you must ask user to choose from one of these 1. open PR merge to dev 2. just push, no merge 3. stop here").

**Never land a repo without its rules file.** No file means you ask the user, write the file, and get their yes on it before any commit or push in that repo.

## Step 0 — Find the repos

1. The ticket's or plan's `## Repos` table lists every repo and worktree the work touched. Use it.
2. No table → the current repo, plus each submodule (`git submodule status`) that has changes.
3. Order: other repos and submodules first, the repo holding their gitlinks last, so its gitlink commit points at commits that already exist.

## Step 1 — Load or create each repo's rules

For each repo, read `<repo>/.claude/finishing-development.md`.

- **It exists** → use it for committing and pushing. Show the user one line per repo: the repo and the rules it will follow.
- **Its `Land:` line says merge** → that line no longer counts; Step 3c asks instead. Tell the user in one line that the file still says merge.
- **It is missing** → stop and ask the user for this repo's rules, with the questions below. Offer the defaults from "Default rules" as the suggested answer, never apply them on your own. Write their answers to `<repo>/.claude/finishing-development.md` in the format below, show the file, and land that repo only after they confirm it. Ask whether the file itself should be committed in that repo.

Questions, one set per repo that has no file:

| Question | Example answer |
|---|---|
| Target branch | `dev` |
| Commit message style | conventional, `feat(import): …` |
| Push the feature branch? | yes, set upstream |
| PR tool and reviewers | `az repos pr create`, reviewer you |
| Before landing | run `pytest -m mock_unit` |
| Never | force-push, commit `.env` |
| After landing | bump the gitlink in the wrapper repo |

### File format

```markdown
# Finishing rules — <repo name>

Target branch: dev
Commit message: conventional, like `feat(import): gate data import on DataImport.Modify`
Push feature branch: yes, `git push -u origin <branch>`
PR: `az repos pr create --target-branch dev --reviewers <email>`, or `gh pr create --base dev`
Before landing: <checks to run, or "none">
Never: force-push; commit `.env`
After landing: <follow-ups, or "none">
Commit this file: yes | no
```

## Step 2 — Archive active OpenSpec changes (if any)

If there is an active, fully-implemented OpenSpec change, archive it with `opsx:archive` (or `openspec-archive-change`) before committing, so the archive lands in the same commit. No active change → skip.

## Step 3 — Land each repo, in order

For each repo, do what its `finishing-development.md` says for committing and pushing, in the order below. A rule the file does not cover → ask the user; never guess.

### 3a — Commit in small batches

- One commit per logical change, like the migration in one, the endpoint in the next, its tests with it.
- Stage by path with `git add <paths>`, never one `git add -A` for the whole diff.
- Use the message style from the rules file.

### 3b — Push the feature branch

- `git push -u origin <current>` when the rules say push. You do not have to ask for this.

### 3c — Ask how it lands, one question per repo

First check how it would merge, without switching branch: never `git checkout` the target (it is often checked out in another worktree, and switching is forbidden).

```bash
git fetch origin "$TARGET"
git merge-tree --write-tree "origin/$TARGET" HEAD >/dev/null && echo clean || echo conflict
git log --oneline "origin/$TARGET..HEAD"   # what a PR would bring in
```

Then ask with `AskUserQuestion`, one call per repo, these three options in this order, none marked Recommended:

1. `Open a PR to merge into <target>` — the PR is opened, never completed
2. `Just push, no merge` — the branch stays pushed, nothing else
3. `Stop here` — nothing more in this repo

- Put the facts in the question: the repo, the target, the commit count, clean or conflict, and commits the branch carries from another branch that is not on the target yet.
- `Other` text is the answer in the user's own words; follow what it says. A merge the user types themselves, naming the target, is their instruction, not this command's choice: do that one merge without switching branch, like the AIO root's "merge directly to origin/dev" (2026-11-10), with `C=$(git commit-tree "$(git merge-tree --write-tree origin/$TARGET HEAD)" -p origin/$TARGET -p HEAD -m "Merge branch '$CURRENT' into $TARGET")`, `git push origin "${C}:refs/heads/$TARGET"`, then `git merge-base --is-ancestor HEAD origin/$TARGET` to prove it landed; a rejected push is never forced.
- A dismissed question or a denied call → `Stop here`.
- Each repo gets its own question.

### 3d — Open the PR, when picked

- Open it with the rules file's `PR:` line, or ask for the tool and reviewers when the file has none.
- Never complete it, never turn on auto-complete or auto-merge, never vote on it.
- A conflict from 3c → open the PR anyway and say it conflicts, or ask; never resolve it by merging the target into the branch without the user asking.
- Give the user the PR's link.

## Step 4 — Clean up what this session left running

Run it after every repo is done, whatever the user picked, since the "Before landing" checks may still need the servers or the database.

- Follow `~/.claude/commands/dev/cleanup.md` from its step 1: list, show the table, ask once, stop what the user picked
- Nothing from this session is still running → one line, move on
- You cannot ask, like when running as a sub-agent → show the table only, stop nothing, and tell the user to run `/dev:cleanup`

## Default rules

Offered as the suggested answer in Step 1, never applied without the user's yes.

| Rule | Default |
|---|---|
| Target | the `<target>` argument, else `dev`, else `master` / `main` |
| Commit | small batches staged by path, skip when the tree is clean |
| Push | `git push -u origin <current>` |
| Land | the Step 3c question; never a merge |

## Safety

- Never merge: no `git merge` into the target, no push to `refs/heads/<target>`, no PR completed, auto-completed or auto-merged. A rules file, a plan, a `/goal`, `/dev:full-dev-cycle` or bypass permissions mode cannot turn this off.
- Never land a repo whose `.claude/finishing-development.md` is missing or not yet confirmed by the user.
- Never force-push.
- Confirm `git status` is clean and each push succeeded before declaring done, repo by repo.

## Cross-References

- Archiving → `opsx:archive`, `openspec-archive-change`
- Stopping what the session left running → `dev:cleanup`
- Methodology this closes out → `dev:development-guideline`
- Parallel worktree integration that precedes this → `dev:parallel-development`
- End-to-end orchestration → `dev:full-dev-cycle`
