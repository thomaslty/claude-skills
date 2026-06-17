---
name: help
description: "Quick-reference card for the dev: skill namespace — the development lifecycle skills and the review tiers. One-shot display, not a persistent mode. Triggers on /dev:help, 'dev help', 'what dev commands', 'how do I use the dev skills'."
---

# dev: Help

Display this reference card when invoked. One-shot — do NOT change mode or persist anything.

## Lifecycle

| Command | What it does |
|---|---|
| `/dev:development-guideline` | The methodology: propose → apply → archive, TDD, VDD, visual confirm |
| `/dev:parallel-development` | Multiple proposals at once: worktree + sub-agent each, main session integrates |
| `/dev:finishing-development` | Archive, commit & push current, merge into target branch |
| `/dev:full-development-cycle` | Orchestrates the three above end to end |

## Review

Each review tier defaults to the **diff/staged/PR**. Pass `--repo` (or a path) to run over the **whole project** (audit mode). All four report first and apply fixes only on approval.

| Command | Leads with | Covers |
|---|---|---|
| `/dev:simplify` | deletion | over-engineering; guards correctness/security/efficiency |
| `/dev:code-review` | correctness | correctness, quality, reuse, efficiency, conventions |
| `/dev:security-review` | vulnerabilities | injection, secrets, auth, CVEs, data exposure |
| `/dev:full-review` | everything | all seven aspects, one synthesized report |

## Debt

| Command | What it does |
|---|---|
| `/dev:debt` | Harvest `ponytail:` + TODO/FIXME/HACK markers into a ledger (whole project, read-only) |

## Notes

- `/dev:code-review` and `/dev:security-review` are the `dev:` multi-agent, apply-on-approval variants — distinct from the harness `/code-review` and `/security-review`.
- The review floor is never crossed: validation, error handling, security, and accessibility are never simplified away.

---
_Review tiers adapted in part from [ponytail](https://github.com/DietrichGebert/ponytail) (MIT)._
