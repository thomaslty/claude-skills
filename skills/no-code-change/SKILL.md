---
name: no-code-change
description: >-
  Use when the user asks to analyze, summarize, gather information, or understand code
  before making changes — or when phrasing suggests they want to see before acting, such as
  "gather me summary", "show me the detail", "let me review first", "what would change",
  or any exploratory request. Also use proactively when the user's intent is ambiguous
  between exploring and changing.
---

# No-Code-Change Mode

## Core Rule

**Show everything. Change nothing.**

Read, analyze, summarize, and present — but NEVER edit, write, or create files unless the user
explicitly authorizes changes.

## What Counts as Authorization

The user must clearly direct you to act:
- "Make the change" / "Go ahead" / "Do it"
- "Fix it" / "Apply that" / "Update it"
- "Write it" / "Create the file"

These are NOT authorization:
- "Can you fix this?" — still a question
- "That looks right" — acknowledgment, not a directive
- "What would you change?" — requesting information
- "Ok" or silence — just acknowledgment

**When in doubt, ask:** "Want me to go ahead and make this change?"

## Workflow

1. **Gather** — read files, check git state, understand scope
2. **Summarize** — present clear, concise findings
3. **Propose** — describe what you WOULD change (files, lines, nature of change) without doing it
4. **Wait** — stop and let the user review
5. **Act** — only when the user explicitly says so

## Presentation Format

For code analysis, always include:
- What the code does now
- What could/should change
- Which files and lines are affected
- Impact and risk

Lead with key findings. Put supporting details and open questions after.

## Red Flags — STOP Before You Act

If you're about to call Edit, Write, or NotebookEdit — STOP.
If you're thinking "I'll just quickly fix this" — STOP.
If you're about to create a file to illustrate — STOP.

Present your findings as text instead.
