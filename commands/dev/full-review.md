---
name: full-review
description: "Use for a comprehensive review across every lens — over-engineering, correctness, quality, reuse, efficiency, security, and conventions — in one synthesized report. Triggers on 'full review', 'review everything', 'thorough review', 'complete code review', or /dev:full-review. Reviews the diff by default; pass --repo (or a path) for the whole project (audit mode). Reports first, applies fixes only on approval."
---

# Full Review

## Overview

The union tier of the `dev:` review family. Runs all seven aspects together and synthesizes one prioritized report. Use it when you want a single comprehensive pass rather than a focused tier.

| Aspect | Core question |
|---|---|
| Over-engineering | What can we delete? |
| Correctness | Does it do the right thing? |
| Quality | Readable / maintainable? |
| Reuse | Reinventing existing code? |
| Efficiency | Wasteful algorithms / queries? |
| Security | Exploitable? |
| Conventions | Follows project standards? |

## Scope

- **Default — the change:** `git diff`, then `git diff --staged`; or an explicit PR / file set.
- **`--repo` or a path — the whole project (audit mode):** scan the tree (skip `node_modules`, `.git`, build output). Rank biggest impact first.

If no diff and no scope is given, ask what to review.

## Engine

Launch one specialist agent per aspect in parallel (single message, all seven). Each returns findings with `file:line`. Then synthesize:

1. **Deduplicate** — merge findings multiple aspects flagged; note consensus (higher confidence).
2. **Prioritize** — Critical (security holes, correctness bugs, data loss) → Important (perf, maintainability, missing tests) → Suggestions (style, minor cuts).
3. The Correctness aspect verifies library/API usage against real docs; Reuse searches the codebase first; Security verifies against CWE/OWASP.

## Output

```
# Full Review — <scope>
Aspects: over-engineering, correctness, quality, reuse, efficiency, security, conventions

## Critical
- [file:line] issue — _aspect(s)_ | _confidence_
## Important
## Suggestions

## Strengths
## Complexity scorecard
net: -<N> lines, -<M> deps possible.

## Verdict
<one line>
```

## Fix — on approval only

Present the full report and stop. Applying a broad cross-cutting sweep at once is risky, so apply **per section on approval** — confirm which findings to act on, then make those edits. Never auto-fix before approval. Honor the floor: never simplify away validation, error handling, security, or accessibility.

## Cross-References

- Focused tiers → `dev:simplify`, `dev:code-review`, `dev:security-review`
- Track deferred shortcuts → `dev:debt`
- All review commands at a glance → `dev:help`

---
_Synthesis engine and over-engineering lens adapted in part from [ponytail](https://github.com/DietrichGebert/ponytail) (MIT)._
