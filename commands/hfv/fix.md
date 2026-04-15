---
name: fix
description: "Implement a minimal, targeted fix for an accepted HFV hypothesis — surgical code changes plus diagnostic logging, then stop for user verification."
---

# HFV Fix — Implement and Stop

Implement the minimal change that tests a hypothesis, then **stop for user verification**.

## Prerequisites

A hypothesis file should already exist in `hfv/<issue>/hypothesis-<desc>.md` with status `pending`. If not, use `hfv:hypothesis` first.

<HOOK-SAFETY>
A pre-tool-use security hook scans ALL file-write content for security-sensitive substrings
related to: Python binary serialization, dynamic code evaluation, child process spawning,
OS command injection, and unsafe DOM manipulation.

When writing or updating hypothesis markdown files, **do not include literal function names,
module names, or API calls** that relate to these security patterns. Instead:
- Use descriptive references: "Python's binary serialization module", "JavaScript's dynamic
  code evaluation function", "Node's child process spawning API", etc.
- Reference code by file path and line number rather than inlining:
  `See server.py:42 — uses unsafe deserialization`
- For evidence sections, describe WHAT the code does rather than quoting the literal tokens.

This avoids false-positive blocks from the security-guidance plugin without weakening the
actual security checks on real code files.
</HOOK-SAFETY>

## Phase: FIX

Implement the minimal change that tests this hypothesis:

1. **Read the hypothesis file** to understand what's being tested
2. **Change as little as possible** — isolate the variable
3. **Add diagnostic logging** if the fix alone won't produce a clear verification signal
4. **Explain every line changed** and why
5. **Update the hypothesis file's Fix section:**

```markdown
## Fix

**File:** `<path>:<lines changed>`
**Change:** <what was changed and why>

## Verification Guide

**How to verify:**
1. <specific steps>
2. <what to look for>

**If correct:**
- <expected observable outcome>

**If wrong:**
- <what user will see instead>
- <what new information this gives us>
```

## Phase: STOP

**STOP HERE.** Do NOT proceed to another hypothesis. Wait for user verification results.

**Red flags that you're about to violate this:**
- "While we wait, let me also fix..."
- "Another thing that could help..."
- "Let me also add..."
- "Just in case, I'll also..."

Present to the user:
1. What was changed and why
2. The verification guide from the hypothesis file
3. Ask them to verify and report back

## When User Reports Results

Update the hypothesis file's Result section:

```markdown
## Result

**Outcome:** CONFIRMED | DENIED | PARTIAL
**Observed:** <what actually happened>
**New evidence:** <what we learned>
```

Then:
- **CONFIRMED** → use `hfv:archive` to archive the resolved issue
- **DENIED** → update status to `denied`, go back to `hfv:hypothesis` with new evidence
- **PARTIAL** → update status to `tested`, go back to `hfv:hypothesis` noting what improved
