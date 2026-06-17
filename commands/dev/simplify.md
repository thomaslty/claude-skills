---
name: simplify
description: "Use to review code for over-engineering — what to delete, simplify, or replace with stdlib/native equivalents. Triggers on 'simplify this', 'review for over-engineering', 'what can we delete', 'is this over-engineered', or /dev:simplify. Reviews the diff by default; pass --repo (or a path) to scan the whole project (audit mode). Reports first, applies cuts only on approval."
---

# Simplify

## Overview

A code review with one obsession: **what can we delete?** Channels a lazy senior dev — the best code is the code never written. Hunts reinvented stdlib, needless dependencies, speculative abstractions, and dead flexibility. The diff's best outcome is getting shorter.

This is the over-engineering tier of the `dev:` review family. Correctness, quality, and security have their own tiers (`dev:code-review`, `dev:security-review`); this one only hunts complexity.

## Scope

- **Default — the change:** `git diff`, then `git diff --staged`; or an explicit PR / file set if given.
- **`--repo` or a path — the whole project (audit mode):** scan the entire tree (skip `node_modules`, `.git`, build output). Rank findings biggest-cut-first.

If no diff and no scope is given, ask what to review.

## Engine

Run specialist agents in parallel (single message), then synthesize:

- **Headline lens — over-engineering.** Find everything deletable using the tags below.
- **Guardrail lenses — correctness, security, efficiency.** These do NOT hunt for issues; they only veto a proposed cut that would change behavior, open a hole, or regress performance. A cut that trips a guardrail is dropped or downgraded to a note.

## Tags

One line per finding. `<file>:L<line>: <tag> <what>. <replacement>.`

| Tag | Means | Replacement |
|---|---|---|
| `delete:` | dead code, unused flexibility, speculative feature | nothing |
| `stdlib:` | hand-rolled thing the standard library ships | name the function |
| `native:` | dep or code doing what the platform already does | name the feature |
| `yagni:` | abstraction with one impl, config nobody sets | inline it |
| `shrink:` | same logic, fewer lines | show the shorter form |

## Examples

✅ `repo.py:L88: yagni: AbstractRepository with one implementation. Inline it until a second exists.`
✅ `L4: native: moment.js imported for one format call. Intl.DateTimeFormat, 0 deps.`
✅ `L52-71: delete: retry wrapper around an idempotent local call. Nothing replaces it.`

❌ "This class might be more complex than necessary, have you considered whether all these rules are needed?"

## Output

Findings ranked biggest-cut-first, each one line with `file:line`. End with the only metric that matters:

`net: -<N> lines, -<M> deps possible.`

Nothing to cut: `Lean already. Ship.` and stop.

## Fix — on approval only

1. Present the findings report and stop.
2. On explicit approval, apply the approved cuts (and only those). Re-run the guardrail check on each before applying.
3. Leave a `// ponytail: <ceiling>, <upgrade path>` comment on any simplification with a known ceiling, so `dev:debt` can track it.

## Never simplify away

Input validation at trust boundaries, error handling that prevents data loss, security measures, accessibility basics, or anything explicitly requested. A single smoke test or `assert`-based self-check is the minimum, not bloat — never flag it for deletion. User wants the full version → build it, no re-arguing.

## Cross-References

- Correctness / quality → `dev:code-review`
- Security → `dev:security-review`
- Everything at once → `dev:full-review`
- Track deferred shortcuts → `dev:debt`
- Harness quality-only variant → `/simplify`

---
_Over-engineering lens adapted from [ponytail](https://github.com/DietrichGebert/ponytail) (MIT)._
