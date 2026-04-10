---
name: hypothesis
description: "Deep exploration and hypothesis formation only — gathers evidence and forms a hypothesis without making any code changes. Use when you need to understand a problem before committing to a fix."
---

# HFV Hypothesis — Explore and Hypothesize Only

Deep investigation mode: gather evidence and form exactly one hypothesis. **No code changes.**

<HARD-GATE>
Do NOT modify any source code, configuration, or project files (other than creating the hypothesis artifact in `hfv/`). This phase is purely analytical.
</HARD-GATE>

## When to Use

- Starting a new investigation and want to understand before changing anything
- Problem is complex and you want to explore before committing to a direction
- User wants to review the hypothesis before any code is touched
- Multiple possible causes and you need to narrow down

## Phase 1: EXPLORE

Gather all available evidence before forming a hypothesis:
- Read error logs, stack traces, debug output
- Read relevant source code and configuration
- Check documentation for the technology involved
- Review environment differences (JDK versions, OS, etc.)
- Search for similar issues, known bugs, or changelogs

**Be thorough.** The quality of the hypothesis depends on the quality of evidence gathered.

**Output:** Summary of evidence collected, organized by relevance.

## Phase 2: HYPOTHESIZE

Form exactly ONE hypothesis. Write it to `hfv/<issue>/hypothesis-<desc>.md`:

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

_To be filled during fix phase (use `hfv:fix`)_

## Verification Guide

_To be filled during fix phase (use `hfv:fix`)_

## Result

_To be filled after user verification_
```

**Priority order when multiple hypotheses exist:**
1. Highest confidence first
2. Among equal confidence, easiest to verify first
3. Among equal ease, smallest blast radius first

## Phase 3: VALIDATE

Before presenting the hypothesis, run a quick pre-filter using two parallel sub-agents to catch obviously wrong hypotheses early.

Dispatch both agents simultaneously using the Agent tool:

**Agent 1 — Code Review:**
> Re-read the hypothesis I just formed: [hypothesis summary]. Trace the relevant code paths
> in [files] and look for: (1) evidence that contradicts this hypothesis, (2) assumptions
> that don't hold in the actual code, (3) a simpler explanation I may have missed. Report
> what you find in under 200 words.

**Agent 2 — Online Research:**
> Search online for: [error/symptom] caused by [hypothesized cause]. Check known issues,
> official docs, changelogs, and community discussions. Does external evidence support or
> contradict this hypothesis? Report in under 200 words.

**After both return:**
- Either raises a concrete contradiction → incorporate into the hypothesis's "Contradicting"
  evidence, reconsider confidence level, and revise if warranted
- Both support → proceed with increased confidence
- Inconclusive → note that and proceed as-is

This is a lightweight sanity check, not a deep investigation. Keep it fast.

## Output

Present to the user:
1. Evidence summary
2. The hypothesis with confidence level
3. Validation results (what the two agents found)
4. Proposed fix approach (described, not implemented)
5. Ask: "Should I proceed with `hfv:fix` to implement this?"

## Red Flags

If you catch yourself about to:
- Edit a source file — STOP. This is hypothesis-only mode.
- "Quick fix while I'm here" — STOP.
- Skip evidence gathering because the cause seems obvious — STOP. Gather evidence anyway.
