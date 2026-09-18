---
name: investigate
description: "Use to investigate an open question or unexplained behaviour — gather cited evidence, form competing hypotheses, rank them by evidence, refute the leading one, then report two sections only: the root cause in plain English, and the ranked fix options with one marked as picked. Triggers on 'investigate', 'why is this happening', 'where did this come from', 'dig into this', 'figure out what's going on', or /dev:investigate. Strictly read-only: changes no file, runs no state-changing command. Hand off to hfv:fix to apply the picked fix."
---

# Investigate

## Overview

The detective tier of the `dev:` family. The review tiers judge code you already have; this one answers a question you cannot yet answer — why did this happen, where did this come from, what is actually true here.

It ends in no code change. "I don't know, and here is what would tell us" is a valid ending.

**The report is two sections: Root Cause and Solution. Nothing else prints.** Everything in phases 1–4 is how you earn those two sections — evidence ledgers, hypothesis tables and refutation notes stay in your head. If a fact matters, it shows up as a real value inside the Root Cause table, not as its own section.

## HARD GATE — read only

| Allowed | Forbidden |
|---|---|
| Read, Grep, Glob | Edit, Write, NotebookEdit |
| `git log/blame/show/diff` | `git` commands that write |
| Read-only queries | Any INSERT/UPDATE/DELETE |
| WebSearch, WebFetch, context7 | Restarting or rebuilding |
| Reading logs already on disk | Anything that mutates state |

You write no file — not even a report file — unless the user asks for one. Present in chat.

If a probe would change state, do not run it. Say so in one line at the end and let the user run it.

Proposing a fix is allowed. Applying one is not.

## Scope

The user's question. If they gave only a symptom, ask two things before starting: what exactly did you see, and how do you know. Then proceed.

---

# Working phases — these do not print

Phases 1–4 produce no output of their own. Run them fully, then throw the scaffolding away.

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
- Facts only here. Explanations wait for phase 5.

## Phase 3 — HYPOTHESIZE

Form 2–4 **competing** hypotheses. Rank them by weight of evidence, not by how clever they sound.

Always include the boring one: stale cache, wrong file read, config not loaded, old build still running, the data was always like that.

For each: what supports it, what contradicts it, and what single check would separate it from the others.

## Phase 4 — REFUTE

Take the leader and try to kill it. Dispatch a devil's-advocate agent whose job is to find the fact that makes it impossible, plus any simpler explanation that fits the same evidence.

Run the cheap read-only checks that would falsify it.

- Leader survives → it is your root cause.
- Leader dies → promote the next one and refute that.
- All die → say so, in one paragraph, and stop. Do not invent a root cause to fill the template.

Do not write the report for a hypothesis that has not survived this phase.

---

# The report — two sections

## Root Cause

### 1. One sentence

What is actually wrong, in plain English, on the first line. No class names, no design-pattern names, no shorthand. The word "no-op" is banned — say what actually happens instead.

If you must use a term of art, define it in the same sentence: "a race — two requests write the same row at the same time and the slower one wins".

> A new `/api/tenant` endpoint was added to **every** app, but nobody told the build's route checker that `/api/tenant` is shared — so it fails rebalance for claiming a URL it does not own.

### 2. The chain

Draw it. ASCII so it renders in the terminal. Trigger on the left, what the reader sees on the right, one box per **real** step. No abstract steps like "processing" or "validation layer".

**The trigger box carries the "why now"** — the commit sha, the deploy, the data change that started it. If nothing changed and it was always broken, the trigger box says that.

```
  [commit 3f98c933]      [what it did]           [what breaks]          [build shows]
  added a tenant    ->   app_factory mounts  ->  rebalance swagger  ->  "tenant" not in
  refresh endpoint       it in EVERY app         now lists tenant       SHARED_PREFIXES
                                                                        -> exit 1
```

Branches and loops are fine. Keep it under ~6 lines tall.

### 3. The table matrix — if it needs one

Skip it when the chain already tells the whole story. Add it when the reader needs the exact files and values.

| Step | What happens | Where | Real value |
|---|---|---|---|
| 1 | mounts tenant router | `app_factory.py:123` | `include_tenant_refresh` |
| 2 | router declares prefix | `tenant_refresh.py:20` | `/api/tenant` |
| 3 | swagger lists prefixes | build step | `app-setting, rebalance, tenant` |
| 4 | exempt list misses it | `check_gateway_routes.py:29` | `{"app-setting"}` |
| 5 | checker exits | `check_gateway_routes.py:113` | `exit 1` |

Rules for this table:
- Every row cites a `file:line`, a sha, a log line, or a URL. No citation, no row.
- Every row carries one **real** number or string — `timeout=30`, `status 504`, `tenant_id=null`. Never "a value" or "some config".
- Cells stay short (~30 chars). This table replaces the prose walkthrough, so the real values have to do the explaining.
- 5 rows or fewer. More than that means you are tracing the design, not the failure.

## Solution

### 1. One sentence

The picked fix, with its `file:line`, on the first line. Say what beats the runner-up in the same sentence if it fits.

> Add `"tenant"` to the exempt list at `check_gateway_routes.py:29` — the same one-line fix `723a3f67` used for app-setting in June.

### 2. Before / after

ASCII, two lines, real code on both sides, ending in what the reader will observe.

```
  before   SHARED_PREFIXES = {"app-setting"}           -> tenant checked -> exit 1
  after    SHARED_PREFIXES = {"app-setting", "tenant"} -> tenant skipped -> exit 0
```

### 3. The options table — if there is a real choice

2–4 options that fix the **cause**, not the symptom. Simplest first. Skip the table only when there is genuinely one way to do it.

| # | Fix | Con | Effort | Risk | Pick |
|---|---|---|---|---|---|
| **1** | **add tenant to the set** | list grows by hand | 2 min | low | **✓ 95%** |
| 2 | auto-detect prefixes | rewrites the checker | 2 hr | medium | 25% |
| 3 | revert 3f98c933 | loses the endpoint | 5 min | low | 10% |
| 4 | add `<when>` arm | all traffic to one app | 10 min | high | 5% |

Column rules:
- **Con** — the single most decisive one. One phrase. Never a semicolon-joined list. There is no Pro column; the sentence above the table already said why the winner wins.
- **Effort** — real units: `5 min`, `1 hr`, `2 days`. Never "some work" or "moderate".
- **Risk** — low / medium / high, judged on blast radius if the fix is wrong.
- **Pick** — 0–100%, how strongly you would pick it. They do not add up to 100. Spread them; if every row lands near the same number you have not chosen, you have listed.

Marking the winner:
- Exactly one ✓ in the whole table. Never two.
- The ✓ row is also the bolded row — `#`, `Fix` and `Pick` cells all bold.
- One row must be the cheap boring one — config, flag, revert. If it genuinely cannot work, keep the row and put the reason in its Con cell.
- A fix that only hides the symptom is allowed only if its Con cell says `stopgap only`.
- If the evidence supports no fix yet, ship no table and say in one line what would settle it.

### 4. Three closing lines

Always these three, in this order, so the pick survives a copy-paste that loses the ✓.

- **Picked — #\<n\>, \<name\>:** `file:line`
- **Verify:** the check that flips, with the real value
- **Rollback:** one line, how to undo it

Add a fourth line, **Still open:**, only when something real stays broken after the fix lands.

## Report template

```
# Summary

## Root Cause

<one plain-English sentence>

<ascii chain — trigger box names the commit / deploy / data change>

| Step | What happens | Where | Real value |
|---|---|---|---|

## Solution

<one sentence: the picked fix + file:line>

<ascii before / after>

| # | Fix | Con | Effort | Risk | Pick |
|---|---|---|---|---|---|

- **Picked — #<n>, <name>:** <file:line>
- **Verify:** <the check + the real value>
- **Rollback:** <one line>
```

Aim for ~30 lines. If it runs past 50, you are reporting your investigation instead of its answer.

## Confidence — you hold it, you do not print it

| Level | Means |
|---|---|
| High | Direct evidence, refutation failed |
| Medium | Consistent, no direct proof |
| Low | Best of weak options |

No confidence line prints. It shows up in the Pick column instead: **Low confidence caps every Pick at 50%** — you cannot strongly pick a fix for a cause you have not established. If you are at Low, say so in the Root Cause sentence itself ("best explanation, not proven:").

## Hand-off

| You want | Use |
|---|---|
| Apply the picked fix | `hfv:fix` |
| More options + trade-offs | `propose` |
| Prove the trigger first | `hfv:reproduce` |
| Judge the code itself | `dev:code-review` |

## Red flags — STOP

- About to edit a file → this skill is read-only, even for the fix you just picked.
- Printing an evidence ledger, a hypothesis table or a refutation write-up → cut it, the report is two sections.
- One hypothesis only → you skipped phase 3; there is always a boring alternative.
- Skipping refutation because the answer is obvious → obvious answers are the ones that survive refutation, so run it.
- A claim with no `file:line`, sha, or URL → it is a guess, label it as one.
- A chain step or table row with no real value → you are describing the design, not the failure.
- Root cause written in jargon → rewrite it for someone who has never opened the repo.
- Two ✓ marks, or no ✓ at all → pick one.
- Every Pick near the same number → you have not ranked, you have listed.
- Starting the fix "while I'm here" → hand off instead.

---
_Part of the `dev:` family; report shape is deliberately shorter than the review tiers._
