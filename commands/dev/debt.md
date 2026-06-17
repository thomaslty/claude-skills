---
name: debt
description: "Harvest deliberate shortcuts and deferrals into a debt ledger so 'later' doesn't quietly become 'never'. Scans the codebase for ponytail: markers plus TODO / FIXME / HACK comments. Triggers on 'tech debt', 'list the shortcuts', 'what did we defer', 'debt ledger', 'ponytail debt', or /dev:debt. One-shot report over the whole project; changes nothing unless you ask it to write the ledger to a file."
---

# Debt

## Overview

Deliberate shortcuts get marked in code — a `ponytail:` comment naming a ceiling and upgrade path, or a `TODO`/`FIXME`/`HACK`. This collects them into one ledger so a deferral can't silently rot into permanence. Whole-project, read-only.

## Scan

Grep the repo for comment markers, skipping `node_modules`, `.git`, and build output:

```bash
grep -rnE '(#|//|/\*) ?(ponytail:|TODO|FIXME|HACK)' . \
  --exclude-dir={node_modules,.git,dist,build,.next,target}
```

Add other comment prefixes if the stack uses them. Each hit is one ledger row. The marker prefix keeps prose that merely mentions the convention out of the ledger.

## Output

One row per marker, grouped by file:

`<file>:<line> — <what was deferred>. ceiling: <limit named>. upgrade: <trigger to revisit>.`

- For `ponytail:` markers, the convention is `ponytail: <ceiling>, <upgrade path>` — pull both straight from the comment.
- For `TODO`/`FIXME`/`HACK`, use the comment text as the "what"; ceiling/upgrade are usually absent.
- Flag the rot risk: any marker with **no upgrade path or trigger** gets a `no-trigger` tag — those are the ones that silently rot.
- Want an owner per row? Add `git blame -L<line>,<line>`.

End with: `<N> markers, <M> with no trigger.`
Nothing found: `No tracked debt. Clean ledger.`

## Boundaries

Reads and reports only — changes nothing. To persist it, ask and it writes the ledger to `TECH-DEBT.md`. One-shot.

## Cross-References

- Leaves `ponytail:` markers when applying cuts → `dev:simplify`, `dev:full-review`
- All `dev:` commands → `dev:help`

---
_Adapted from [ponytail](https://github.com/DietrichGebert/ponytail) `ponytail-debt` (MIT)._
