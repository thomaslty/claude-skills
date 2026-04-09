---
description: Start systematic debugging — one hypothesis, one fix, one verification at a time
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
argument-hint: [error description or log output]
---

Activate the HFV (Hypothesis-Fix-Verify) debugging workflow.

You are entering a disciplined debugging mode. Follow the phases below strictly — never skip ahead or stack multiple fixes.

All artifacts go in the project directory under `hfv/<issue-name>/`.

## Phase 1: EXPLORE

Gather all available evidence before forming any hypothesis:
- Read error logs, stack traces, and debug output provided by the user (or in the argument)
- Read relevant source code paths and configuration
- Check environment differences (JDK versions, OS, etc.)
- Review documentation for the technology involved

**Output a summary** of evidence collected, organized by relevance.

## Phase 2: HYPOTHESIZE

Form exactly ONE hypothesis. Write it to `hfv/<issue>/hypothesis-<desc>.md` using this template:

```markdown
---
status: pending
created: YYYY-MM-DD
---

# Hypothesis: <one-sentence statement>

## Evidence

### Supporting
- <what supports this hypothesis>

### Contradicting
- <what contradicts it — be honest>

### Confidence: Low | Medium | High

## Fix

_To be filled during fix phase_

## Verification Guide

_To be filled during fix phase_

## Result

_To be filled after user verification_
```

**Priority when multiple hypotheses exist:** highest confidence first, then easiest to verify, then smallest blast radius.

## Phase 3: FIX

Implement the **minimal** change that tests this hypothesis:
- Change as little as possible — isolate the variable
- Add diagnostic logging if the fix alone won't produce a clear signal
- Explain every line changed and why
- Update the hypothesis file's Fix and Verification Guide sections

## Phase 4: STOP

**STOP HERE.** Do NOT proceed to another hypothesis. Wait for user verification.

Red flags you're about to violate this:
- "While we wait, let me also fix..."
- "Another thing that could help..."
- "Let me also add..."
- "Just in case, I'll also..."

## Phase 5: EVALUATE (after user reports back)

Update the hypothesis file's Result section, then:
- **CONFIRMED** → Archive: move issue dir to `hfv/archive/<issue-name>/`
- **DENIED** → Back to EXPLORE with new evidence
- **PARTIAL** → Back to EXPLORE, note what improved
- **New error** → Revert first, then EXPLORE
