---
name: 3-review
description: "Review phase: one fresh dev-reviewer reads the diff once with every lens (correctness, feature, completeness, security basics), plus a security reviewer at xhigh when the change is risky, against the plan. Reports T0 issues only, and shows each one right here in the terminal with its root cause, impact and fix. You reply fix / skip per finding in chat. After the fixes, the re-review reads only what the fixes changed, once. Read-only until you reply. Triggers on /dev:3-review, 'review the work', 'review this ticket'."
argument-hint: "[plan/<slug>/plan.md] [--base <ref>]"
---

# 3 — Review

You are the coordinator. The review runs in fresh `dev-reviewer` agents. Nothing is changed until the user replies.

Review talks to the user in the terminal only. No HTML page, no JSON to copy.

One reviewer reads the diff once with every lens, not four reviewers with one each. On the offload test, 16 single-lens reviews cost 10.6M tokens for 4 different bugs: correctness and feature reported the same bug every time either found one, and completeness found nothing in 4 runs. Fresh context still matters, so the reviewer is never the agent that wrote the code.

## Steps

1. Plan: from `$ARGUMENTS`, or the only plan in `plan/`, or ask in one line.
2. Base: `--base <ref>` if given, otherwise the plan's `Base:` line, which `/dev:2-implement` writes before the build. A plan without one → `git merge-base HEAD origin/HEAD` (fall back to `master` or `main`). A repo with no commit yet → `4b825dc642cb6eb9a060e54bf8d69288fbee4904`, git's empty tree.
3. Card: `python3 ~/.claude/scripts/dev/orca-card.py review`
4. Completeness by script, before any agent:
   - `python3 ~/.claude/scripts/dev/plan-status.py plan/<slug>/plan.md` must say `done: true`
   - and, unless the plan has `Size: small`, `openspec status --change <slug> --json` must show every task done
   - Either one fails → that is finding `comp-1`, with the steps `left` as its cause. Write it to `dev/<slug>/review/scripts.json` in the reviewer's JSON shape. Otherwise write `[]` there.
5. Spawn the reviewers in ONE message, each with `plan` and `base`:
   - always one `dev-reviewer` with `lens: all`, at `effort: high`
   - the change is risky → also one with `lens: security`, at `effort: xhigh`. Risky is any of: the plan has a `Risk: high` step; a changed file is under `## Claude only` or `## Deep pass` in `.claude/risky.md` (`git diff --name-only <base>` plus the untracked files); or the repo has no `.claude/risky.md`
   - the plan has `Offload: local` → in the same turn, start qwen's pre-pass, the way "Review pre-pass" in `~/.claude/commands/dev/offload-to-localLLM.md` says. It runs next to the reviewers and never changes a file.
6. Save each agent's JSON array verbatim as `dev/<slug>/review/all.json` and `dev/<slug>/review/security.json`. Do not edit, merge or rewrite them. On a re-review, first move the last round's files into `dev/<slug>/review/round<n>/`.
7. Merge them:

```bash
python3 ~/.claude/scripts/dev/review-findings.py --plan plan/<slug>/plan.md dev/<slug>/review/{scripts,all,security}.json
```

   Leave out a file no agent wrote. It merges findings at the same `file:line` into one (listing every lens), writes `dev/<slug>/review/findings.json`, and writes `dev/<slug>/review/findings.md` for the terminal.
   - `findings: 0` and no qwen pre-pass running → tell the user "review clean: <n> reviewers, 0 T0 issues", run `orca-card.py ready`, and stop.
8. Print `dev/<slug>/review/findings.md` in the terminal as it is, as soon as it is ready: the count by lens, then every finding with its `Where`, root cause, impact and fix. Never cut it to titles. Open no file or diff tabs; the `Where` path is the link. Never wait for qwen's pre-pass: its items follow before the user replies, the way the offload skill says.
9. Run `orca-card.py waiting-review`. End with one line, like: "Reply here, like `fix all` or `sec-1 fix, cor-2 skip: we only log ids`." Stop and wait.
10. The user's reply is the answer, typed by the user. A `/goal` or your own plan is never a reply, the way rule 2 in `~/.claude/commands/dev/full-dev-cycle.md` says. A finding it does not mention → ask about just those, in one line. Then:
    - Spawn `dev-convention-learner` at `effort: low` with `phase: review`, `plan`, and `feedback: <the reply verbatim>`. Skipped findings and comments are the strongest signal of what this project does not care about. Inside `/dev:full-dev-cycle`, skip this: the cycle runs one learner at the end.
    - Append a `## Review` section to the plan listing each finding id, its choice, and the comment.
    - If any finding is to be fixed, or the reply asks for something else:
      - snapshot each repo the fixes touch, so the re-review can read only what they change: `python3 ~/.claude/scripts/dev/changes.py snapshot dev/<slug>/review/fix-<round>/<repo> --root <that repo's worktree>`
      - run `orca-card.py fixing`, then fix them the way `## Fixes` in `~/.claude/commands/dev/2-implement.md` says, with `fixes`: those findings from `dev/<slug>/review/findings.json`, plus the user's comments. Findings in 2 or more repos get one `dev-implementer` per repo at the same time. With `Offload: local` there is no implementer: you fix them yourself. The reply is the go-ahead for these fixes.
      - then the re-review (below).

## Re-review

It runs once, and reads only what the fixes changed. On the offload test, round 2 re-read all 21 files to check 2 fixes, and both bugs it found were in the fixed lines.

1. Move this round's review files into `dev/<slug>/review/round<n>/`.
2. For each repo: `python3 ~/.claude/scripts/dev/changes.py diff dev/<slug>/review/fix-<round>/<repo> > dev/<slug>/review/fix-<round>/<repo>.patch`.
3. Spawn one `dev-reviewer` with `lens: all`, `plan`, `diff: <those patch files>` and `fixes: dev/<slug>/review/round<n>/findings.json`, at `effort: high`. A patch touches a risky file or adds a `## Patterns` text from `.claude/risky.md` → also one with `lens: security` and the same `diff`, at `effort: xhigh`. No qwen pre-pass.
4. Merge and print the way steps 6 to 8 say. Then stop: another round starts only when the user asks for it, the way rule 4 in `~/.claude/commands/dev/full-dev-cycle.md` says.

## Cross-References

- Effort for every agent → `## Effort` in `/dev:full-dev-cycle`
- Single-lens deep reviews → `/dev:code-review`, `/dev:security-review`, `/dev:simplify`
- Landing the work → `/dev:finishing-development`
