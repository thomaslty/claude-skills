---
name: archive
description: "Archive a verified HFV fix as successfully resolved — moves the issue directory to the archive with confirmed status."
---

# HFV Archive — Close a Resolved Investigation

Move a confirmed investigation to the archive.

## Prerequisites

A hypothesis in `hfv/<issue>/` should have status `confirmed` (verified by the user).

## Steps

1. **Find the confirmed hypothesis** — look in `hfv/` for the issue directory
2. **Verify the hypothesis file has status confirmed** — if not, ask the user to confirm first
3. **Update the hypothesis file** — ensure the Result section is filled with final outcome
4. **Move the issue directory** to `hfv/archive/<issue-name>/`

```bash
mkdir -p hfv/archive
mv hfv/<issue-name> hfv/archive/<issue-name>
```

4. **Report** what was archived and the key findings

## Output

Present to the user:
- Issue name and hypothesis that resolved it
- Summary of what was learned
- Location of archived artifacts
