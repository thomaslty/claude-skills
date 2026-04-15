---
name: validate-hypothesis
description: "Validate an existing HFV hypothesis using two parallel sub-agents — one reviews the hypothesis against the codebase, one searches online. Use as a quick pre-filter to catch obviously wrong hypotheses before committing to a fix."
---

# HFV Validate Hypothesis

Quick pre-filter: dispatch two parallel sub-agents to sanity-check a hypothesis before
proceeding to fix.

## Prerequisites

A hypothesis file must exist in `hfv/<issue>/hypothesis-<desc>.md` with status `pending`.

<HOOK-SAFETY>
A pre-tool-use security hook scans ALL file-write content for security-sensitive substrings
related to: Python binary serialization, dynamic code evaluation, child process spawning,
OS command injection, and unsafe DOM manipulation.

When updating hypothesis markdown files, **do not include literal function names, module names,
or API calls** that relate to these security patterns. Instead:
- Use descriptive references: "Python's binary serialization module", "JavaScript's dynamic
  code evaluation function", "Node's child process spawning API", etc.
- Reference code by file path and line number rather than inlining:
  `See server.py:42 — uses unsafe deserialization`
- For evidence sections, describe WHAT the code does rather than quoting the literal tokens.

This avoids false-positive blocks from the security-guidance plugin without weakening the
actual security checks on real code files.
</HOOK-SAFETY>

## Steps

1. **Read the hypothesis file** — extract the one-sentence hypothesis, supporting/contradicting
   evidence, and the relevant files

2. **Dispatch two parallel sub-agents:**

   **Agent 1 — Code Review:**
   > Re-read the hypothesis: [hypothesis summary]. Trace the relevant code paths in [files]
   > and look for: (1) evidence that contradicts this hypothesis, (2) assumptions that don't
   > hold in the actual code, (3) a simpler explanation that may have been missed. Report in
   > under 200 words.

   **Agent 2 — Online Research:**
   > Search online for: [error/symptom] caused by [hypothesized cause]. Check known issues,
   > official docs, changelogs, and community discussions. Does external evidence support or
   > contradict this hypothesis? Report in under 200 words.

3. **Evaluate results:**
   - Either agent raises concrete contradiction → update the hypothesis file's "Contradicting"
     evidence, reconsider confidence level, revise if warranted
   - Both support → note validation in the file, proceed with increased confidence
   - Inconclusive → note that and proceed as-is

## Output

Present to the user:
1. Code review agent findings
2. Online research agent findings
3. Updated confidence level (if changed)
4. Recommendation: proceed to `hfv:fix`, revise hypothesis, or form a new one
