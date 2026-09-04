---
name: investigate
description: "Use to investigate an open question or unexplained behaviour — gather cited evidence, form competing hypotheses, rank them by evidence, refute the leading one, then explain the root cause in plain English and rank the fix options with a recommendation. Triggers on 'investigate', 'why is this happening', 'where did this come from', 'dig into this', 'figure out what's going on', or /dev:investigate. Strictly read-only: changes no file, runs no state-changing command. Hand off to hfv:fix to apply the recommended fix."
---

# Investigate

## Overview

The detective tier of the `dev:` family. The review tiers judge code you already have; this one answers a question you cannot yet answer — why did this happen, where did this come from, what is actually true here.

It ends in a verdict, a root cause a newcomer can follow, and ranked fix options. It ends in no code change. "I don't know, and here is what would tell us" is a valid ending.

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

Proposing a fix is allowed. Applying one is not.

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

Do not start phase 5 for a hypothesis that has not survived this phase.

## Phase 5 — ROOT CAUSE

Explain the surviving hypothesis so a colleague who has never opened this repo understands it. Three parts, in this order.

### 5a. One sentence

What is actually wrong, in plain English. No class names, no design-pattern names, no shorthand. The word "no-op" is banned — say what actually happens instead.

If you must use a term of art, define it in the same sentence: "a race — two requests write the same row at the same time and the slower one wins".

### 5b. The chain

Draw it. Trigger on the left, what the user sees on the right, one box per **real** step. No abstract steps like "processing" or "validation layer".

```
  [trigger]        [what the code does]     [what goes wrong]      [what the user sees]
  user hits   ->   reads TIMEOUT from   ->  the var is unset  ->   falls back to 30s,
  /export          os.environ               on the prod pod        request returns 504
```

Branches and loops are fine — keep it ASCII so it renders in the terminal.

### 5c. The table + the worked example

| Step | What happens | Where | Real value |
|---|---|---|---|
| 1 | reads env var | `config.py:22` | `TIMEOUT` unset |
| 2 | falls back | `config.py:24` | `30` |
| 3 | query outruns it | `export.py:88` | 41s |
| 4 | gateway gives up | nginx access log | `504` |

Rules for this table:
- Every row cites a `file:line`, a sha, a log line, or a URL. No citation, no row.
- Every row carries one **real** number or string — `timeout=30`, `status 504`, `tenant_id=null`. Never "a value" or "some config".
- Cells stay short (~30 chars). The meaning goes in the prose below, not inside the cell.

Then write the worked example in prose, under the table: the actual request, the actual values, the actual failure, in order. A reader who has never seen the code must be able to follow it without asking a question. If you cannot write it, you have not found the root cause yet — go back to phase 2.

### 5d. Why now

Say what changed to make it start — a commit sha, a deploy, a data change, a dependency bump. If nothing changed and it was always broken, say that plainly. "Unknown" is allowed; silence is not.

## Phase 6 — SOLUTIONS

2–4 options that fix the **cause** from phase 5, not the symptom. Simplest first.

| # | Fix | Pro | Con | Effort | Risk | Recommend |
|---|---|---|---|---|---|---|
| 1 | set env var on the pod | ships today | lost on redeploy | 5 min | low | 40% |
| 2 | default in `config.py` | survives redeploy | needs a release | 1 hr | low | 90% |
| 3 | drop the timeout | no config at all | slow calls hang | 30 min | high | 10% |

Column rules:
- **Pro / Con** — the single most decisive one each. One phrase. Never a semicolon-joined list.
- **Effort** — real units: `5 min`, `1 hr`, `2 days`. Never "some work" or "moderate".
- **Risk** — low / medium / high, judged on blast radius if the fix is wrong.
- **Recommend** — 0–100%, how strongly you would pick it. They do not add up to 100. Spread them; if every row lands near the same number you have not actually chosen.

Rules:
- One row must be the cheap boring one — config, flag, revert. If it genuinely cannot work, keep the row and put the reason in its Con cell.
- A fix that only hides the symptom is allowed only if its Pro cell says `stopgap`.
- If the evidence supports no fix yet, ship an empty table and give probes instead. An empty solutions table beats a guessed one.

### Recommended fix

Name the winner, then write these five lines in prose. Not a table — this part needs sentences.

| Line | Must contain |
|---|---|
| What to change | `file:line` + the actual change |
| Why this one | beats the runner-up, in one sentence |
| Does not fix | what still hurts after it lands |
| Verify by | the check that flips, + the real value |
| Rollback | one line, how to undo it |

You do not apply it. Hand off.

## Phase 7 — REPORT

```
# Investigation — <question>

## Verdict
<one sentence> — confidence: High | Medium | Low

## Root cause
<one plain-English sentence>

<ascii chain>

| Step | What happens | Where | Real value |
|---|---|---|---|

<worked example, in prose — real request, real values, real failure>

**Why now:** <commit / deploy / data change, or "always broken, just noticed">

## Evidence ledger
| Fact | Source | Weight |
|---|---|---|
| what is true | file:line / sha / URL | strong / weak |

## Hypotheses
| # | Hypothesis | For | Against | Verdict |
|---|---|---|---|---|

## Refutation
<what you tried to kill the leader with, and what happened>

## Fix options
| # | Fix | Pro | Con | Effort | Risk | Recommend |
|---|---|---|---|---|---|---|

## Recommended fix — Option <n>: <name>
- **What to change:** <file:line + the change>
- **Why this one:** <beats the runner-up>
- **Does not fix:** <what still hurts>
- **Verify by:** <the check + the real value>
- **Rollback:** <one line>

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

Never report High on inference alone. Confidence Low caps the Recommend column at 50% — you cannot strongly recommend a fix for a cause you have not established.

## Hand-off

| You want | Use |
|---|---|
| Apply the recommended fix | `hfv:fix` |
| More options + trade-offs | `propose` |
| Prove the trigger first | `hfv:reproduce` |
| Judge the code itself | `dev:code-review` |

## Red flags — STOP

- About to edit a file → this skill is read-only, even for the fix you just recommended.
- One hypothesis only → you skipped phase 3; there is always a boring alternative.
- Skipping refutation because the answer is obvious → obvious answers are the ones that survive refutation, so run it.
- A claim with no `file:line`, sha, or URL → it is a guess, label it as one.
- A chain step or table row with no real value → you are describing the design, not the failure.
- Root cause written in jargon → rewrite it for someone who has never opened the repo.
- One fix option only, or every Recommend near the same number → you have not ranked, you have listed.
- Starting the fix "while I'm here" → hand off instead.

---
_Part of the `dev:` family; report shape follows the review tiers._
