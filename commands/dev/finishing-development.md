---
name: finishing-development
description: "Use when development work is complete and ready to land — archives any active OpenSpec change, commits and pushes the current branch, then merges it back into the target branch and pushes. Takes one optional argument: the target branch to merge into (defaults to the session's starting branch, then falls back dev → master/main)."
---

# Finishing Development

## Overview

The closing ritual for a development session. Three steps, strictly in order: **archive → commit & push current → merge back into target**. Run this only once all work is implemented and visually confirmed (see `dev:development-guideline`).

## Input

One optional argument: `<target branch>` — the branch to merge the finished work into. If omitted, it is resolved automatically (below).

## Target-branch resolution

Resolve the target by walking this priority and stopping at the first branch that **exists**:

| Priority | Candidate | When |
|---|---|---|
| 1 | `<target branch>` arg | An argument was supplied |
| 2 | Current branch | No argument supplied |
| 3 | `dev` | Candidate above does not exist |
| 4 | `master` / `main` | `dev` does not exist |

**Example** — session started on `chore/something`, run with no argument:
- target defaults to `chore/something` (it exists — you are on it) → that is the target;
- had `chore/something` not existed → fall to `dev`;
- had `dev` not existed → fall to `master` (or `main`).

```bash
CURRENT=$(git branch --show-current)
WANT="${1:-$CURRENT}"   # supplied arg, else current branch
exists() { git rev-parse --verify --quiet "refs/heads/$1" >/dev/null || git rev-parse --verify --quiet "refs/remotes/origin/$1" >/dev/null; }
if   exists "$WANT";   then TARGET="$WANT"
elif exists dev;       then TARGET="dev"
elif exists master;    then TARGET="master"
elif exists main;      then TARGET="main"
fi
```

If the resolved `TARGET` equals `CURRENT`, there is nothing to merge — steps 1–2 still run; step 3 is a no-op and you simply stay on the branch.

## Workflow

### Step 1 — Archive active OpenSpec changes (if any)

If there is an active, fully-implemented OpenSpec change, archive it with `opsx:archive` (or `openspec-archive-change`). If there is no active change, skip this step. Archive **before** committing so the archive lands in the same commit.

### Step 2 — Commit & push the current branch

Commit any pending work on `CURRENT`, then push to origin (set upstream on first push):

```bash
git add -A
git commit -m "<message>"        # skip if the tree is already clean
git push -u origin "$CURRENT"
```

### Step 3 — Merge back into the target & push

Only when `TARGET` != `CURRENT`:

```bash
git checkout "$TARGET"
git pull --ff-only origin "$TARGET"   # only if origin/$TARGET exists
git merge --no-ff "$CURRENT"
git push origin "$TARGET"
```

End on `TARGET` (do not switch back to `CURRENT`).

## Safety

- Never force-push.
- If the merge conflicts, **stop and resolve in this session** with full context — never abandon or force the merge.
- Confirm `git status` is clean and each push succeeded before declaring done.

## Cross-References

- Archiving → `opsx:archive`, `openspec-archive-change`
- Methodology this closes out → `dev:development-guideline`
- Parallel worktree integration that precedes this → `dev:parallel-development`
- End-to-end orchestration → `dev:full-development-cycle`
