---
name: investigate
description: "Use to investigate an open question or unexplained behaviour — gather cited evidence, form competing hypotheses, rank them by evidence, then try to refute the leading one. Triggers on 'investigate', 'why is this happening', 'where did this come from', 'dig into this', 'figure out what's going on', or /dev:investigate. Strictly read-only: changes no file, runs no state-changing command. Hand off to hfv:fix or propose to act on the verdict."
---

# Investigate

## Overview

The detective tier of the `dev:` family. The review tiers judge code you already have; this one answers a question you cannot yet answer — why did this happen, where did this come from, what is actually true here.

It ends in a verdict with confidence, not a change. "I don't know, and here is what would tell us" is a valid ending.

## HARD GATE — read only

| Allowed | Forbidden |
|---|---|
| Read, Grep, Glob | Edit, Write, NotebookEdit |
| `git log/blame/show/diff` | `git` commands that write |
| Read-only queries | Any INSERT/UPDATE/DELETE |
| WebSearch, WebFetch, context7 | Restarting or rebuilding |
| Reading logs already on disk | Anything that mutates state |

You write no file — not even a report file — unless the user asks for one. Present in chat.

If a probe would change state, do not run it. Name it in "Next probes" and let the user run it.

## Scope

The user's question. If they gave only a symptom, ask two things before starting: what exactly did you see, and how do you know. Then proceed.

## Phase 1 — FRAME

1. Restate the question in one sentence.
2. Write the **proof bar**: what evidence would settle it, and what would falsify it.
3. List the cheapest probes that touch the proof bar.

If you cannot write the proof bar, the question is too vague — ask, do not guess.

## Phase 2 — SWEEP

Launch lens agents in parallel (single message), then collect. Each returns facts with a citation: `file:line`, a commit sha, a log line, or a URL. **No citation, no evidence.**

| Lens | Digs into |
|---|---|
| Timeline | `git log`, blame, changelogs |
| Runtime | logs, read-only queries, env |
| Code path | trace the call chain |
| External | official docs, issues, CVEs |

Rules:
- The External lens MUST hit real docs or issue trackers (context7 or web), never training data alone.
- A lens that finds nothing says so out loud. Silence is not absence.
- Facts only here. Explanations wait for phase 3.

## Phase 3 — HYPOTHESIZE

Form 2–4 **competing** hypotheses. Rank them by weight of evidence, not by how clever they sound.

Always include the boring one: stale cache, wrong file read, config not loaded, old build still running, the data was always like that.

For each: what supports it, what contradicts it, and what single check would separate it from the others.

## Phase 4 — REFUTE

Take the leader and try to kill it. Dispatch a devil's-advocate agent whose job is to find the fact that makes it impossible, plus any simpler explanation that fits the same evidence.

Run the cheap read-only checks that would falsify it.

- Leader survives → confidence goes up, say why.
- Leader dies → promote the next one and refute that.
- All die → report that, with the evidence that killed each.

## Phase 5 — REPORT

```
# Investigation — <question>

## Verdict
<one sentence> — confidence: High | Medium | Low

## Evidence ledger
| Fact | Source | Weight |
|---|---|---|
| what is true | file:line / sha / URL | strong / weak |

## Hypotheses
| # | Hypothesis | For | Against | Verdict |
|---|---|---|---|---|

## Refutation
<what you tried to kill the leader with, and what happened>

## Unknowns
- <what is still not established, and why it matters>

## Next probes
1. <cheapest thing that would settle an unknown — the user runs it>
```

## Confidence

| Level | Means |
|---|---|
| High | Direct evidence, refutation failed |
| Medium | Consistent, no direct proof |
| Low | Best of weak options |

Never report High on inference alone.

## Hand-off

| You want | Use |
|---|---|
| Fix the cause | `hfv:fix` |
| Options + trade-offs | `propose` |
| Prove the trigger first | `hfv:reproduce` |
| Judge the code itself | `dev:code-review` |

## Red flags — STOP

- About to edit a file → this skill is read-only.
- One hypothesis only → you skipped phase 3; there is always a boring alternative.
- Skipping refutation because the answer is obvious → obvious answers are the ones that survive refutation, so run it.
- A claim with no `file:line`, sha, or URL → it is a guess, label it as one.
- Starting the fix "while I'm here" → hand off instead.

---
_Part of the `dev:` family; report shape follows the review tiers._
