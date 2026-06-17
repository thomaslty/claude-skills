---
name: code-review
description: "Use to review code for correctness and quality — logic bugs, readability, reuse, efficiency, and project conventions. Triggers on 'review this', 'check this code', 'any bugs', 'code review', or /dev:code-review. Reviews the diff by default; pass --repo (or a path) for the whole project (audit mode). Security has its own tier (dev:security-review). Reports first, applies fixes only on approval."
---

# Code Review

## Overview

The correctness-and-quality tier of the `dev:` review family. Headline lens is **does it do the right thing?** — plus quality, reuse, efficiency, and conventions. It does NOT cover security (use `dev:security-review`) or lead with deletion (use `dev:simplify`).

## Scope

- **Default — the change:** `git diff`, then `git diff --staged`; or an explicit PR / file set.
- **`--repo` or a path — the whole project (audit mode):** scan the tree (skip `node_modules`, `.git`, build output).

If no diff and no scope is given, ask what to review.

## Engine

Launch specialist agents in parallel (single message), one per lens, then synthesize. Each returns findings with `file:line` references.

| Lens | Hunts for |
|---|---|
| Correctness | logic bugs, wrong API use vs docs, unhandled edge cases |
| Quality | naming, structure, complexity, readability, dead code |
| Reuse | DRY violations, existing utilities/framework features ignored |
| Efficiency | bad algorithmic complexity, N+1 queries, needless allocations |
| Conventions | language idioms, project standards (CLAUDE.md, linters), tests, types |

The Correctness lens MUST verify key library/API usage against real docs (context7 or web search), not training data alone. The Reuse lens MUST search the codebase for existing patterns before flagging.

## Output

Synthesize into one prioritized report. Deduplicate across lenses; note consensus (2+ lenses → higher confidence).

```
# Code Review — <scope>

## Critical (must fix)
- [file:line] issue — _lens(es)_ | _confidence_

## Important (should fix)
- [file:line] issue — _lens(es)_

## Suggestions
- [file:line] suggestion

## Strengths
- what's done well

## Verdict
<one line: ship / fix critical first / needs rework>
```

## Fix — on approval only

Present the report and stop. On explicit approval, apply the agreed fixes (deferring anything that needs a design decision back to you). Do not auto-fix before approval.

## Cross-References

- Deletion / over-engineering → `dev:simplify`
- Security → `dev:security-review`
- Everything at once → `dev:full-review`

---
_Part of the `dev:` review family; structure adapted in part from [ponytail](https://github.com/DietrichGebert/ponytail) (MIT)._
