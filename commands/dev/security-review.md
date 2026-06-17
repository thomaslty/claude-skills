---
name: security-review
description: "Use to review code for security vulnerabilities — injection, secrets, auth gaps, unsafe input handling, dependency CVEs, and data exposure. Triggers on 'security review', 'is this secure', 'check for vulnerabilities', 'any security issues', or /dev:security-review. Reviews the diff by default; pass --repo (or a path) for the whole project (audit mode). Reports first, applies fixes only on approval."
---

# Security Review

## Overview

The security tier of the `dev:` review family. One lens, exclusively: **is this exploitable?** Correctness and quality go to `dev:code-review`; this pass only hunts vulnerabilities.

## Scope

- **Default — the change:** `git diff`, then `git diff --staged`; or an explicit PR / file set.
- **`--repo` or a path — the whole project (audit mode):** scan the tree (skip `node_modules`, `.git`, build output).

If no diff and no scope is given, ask what to review.

## Engine

Launch specialist agents in parallel (single message), then synthesize. Verify suspected issues against real sources (CWE/OWASP, advisories, library docs) before reporting.

What to hunt:

| Class | Examples |
|---|---|
| Injection | SQL, command, XSS, template, LDAP |
| Input handling | missing validation at trust boundaries, unsafe deserialization |
| Secrets | hardcoded credentials/tokens, secrets in logs |
| AuthN / AuthZ | missing or broken access checks, privilege escalation |
| Traversal / SSRF | path traversal, file inclusion, server-side request forgery |
| Crypto | weak/absent encryption in transit or at rest, bad randomness |
| Dependencies | known CVEs in pinned versions |
| Data exposure | error messages leaking internals, PII in responses/logs |

## Output

Findings ranked by severity, each with `file:line`, a CWE/OWASP reference, and impact.

```
# Security Review — <scope>

## Critical
- [file:line] issue — CWE-XXX — impact — fix

## High
## Medium
## Low

## Verdict
<one line: no blocking issues / fix Critical+High before merge / ...>
```

Nothing found: `No security issues in scope.` and stop.

## Fix — on approval only

Present the report and stop. On explicit approval, apply the agreed remediations. Security fixes touch behavior (auth, validation, crypto) — apply them deliberately, one finding at a time, and re-verify the fix doesn't break the guarded flow.

## Cross-References

- Correctness / quality → `dev:code-review`
- Deletion / over-engineering → `dev:simplify`
- Everything at once → `dev:full-review`
- Heavier built-in pass → `/security-review` (harness)

---
_Part of the `dev:` review family._
