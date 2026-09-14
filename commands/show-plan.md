---
name: show-plan
description: "Show the full current plan — nothing summarised, nothing cut — as a goal line, a box flow diagram, a matrix table of every step, and point-form detail per row. Triggers on 'show me the plan', 'show the full plan', 'what's the plan', 'plan with graph and matrix', or /show-plan. Strictly read-only: changes no file, runs no state-changing command."
allowed-tools: Read, Glob, Grep, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(ls:*), Bash(cat:*)
---

# Show Plan

## Overview

Displays the plan that is already in play. It does not invent one, does not refine one, and does not start executing one.

The output is always the same four blocks, in this order:

1. **Goal** — one sentence.
2. **Graph** — a flow diagram of boxes joined by arrows.
3. **Matrix** — every step as a row.
4. **Detail** — point form, one block per row.

## HARD GATE — read only

| Allowed | Forbidden |
|---|---|
| Read, Grep, Glob | Edit, Write, NotebookEdit |
| `git log/status/diff` | Any `git` command that writes |
| `ls`, `cat` | Running builds, tests, servers |
| Reading plan files | Starting any step of the plan |

You write no file — not even the plan itself — unless the user asks for one. Present in chat.

## Step 1 — find the plan

Look in this order and stop at the first hit:

1. The active plan or todo list in this session.
2. `openspec/changes/*/` — read `proposal.md`, `design.md`, and `tasks.md`.
3. A proposal or plan file named in the conversation.
4. The plan agreed in this conversation but never written down.

Say which source you used, in one line, before the Goal block.

If there is no plan anywhere, say exactly that and stop. Do not draft one.

## Step 2 — FULL means full

Show every step. No "…and 4 more", no "the rest follow the same pattern", no collapsing similar steps into one row.

If the plan has 23 steps, the graph has 23 boxes and the matrix has 23 rows. A long plan is the reason the user asked.

## Step 3 — Goal

One sentence, plain English, no jargon. What is true when the whole plan is done.

Then one line: what is done already, what is left. Real numbers — "4 of 11 steps done".

## Step 4 — Graph

**It is a flow diagram.** Boxes joined by arrows, showing what feeds what. Not a grouped list of boxes. Not a one-line label per step.

Put it in a plain fenced code block. It must render in a terminal, so no mermaid, no HTML, no images — the TUI shows those as raw text.

### The box

Three lines, fixed width, always the same shape:

```
┌────────────────────┐
│ [!] 1  Rebase dev  │   line 1: marker + number + short name
│  107 behind dev    │   line 2: the one real anchor
│  30 min - YOU run  │   line 3: effort + who runs it
└──────────┬─────────┘   bottom edge carries the exit when an arrow leaves
           │
           ▼
```

| Rule | Value |
|---|---|
| Inner width | fixed, 20 chars |
| Lines inside | exactly 3 |
| Boxes side by side | max 3 |
| Whole graph | under 80 columns |

- **Line 1** — status marker, step number, short name. `[x]` done, `[>]` now, `[ ]` next, `[!]` blocked.
- **Line 2** — a real anchor. `rs.py:622` yes. `the SQL file` no. A number works too: `17/11/4 hits`.
- **Line 3** — effort in concrete units, plus owner or blocker. `45 min`, `2 h`, `30 min - YOU run`.

If a name will not fit 18 characters, shorten the name. Never widen the box.

### Charset — Unicode is the default

```
┌ ┐ └ ┘ ─ │ ├ ┤ ┬ ┴ ┼ ▼ ► ●
```

Use ASCII only when the output is going into a file, a PR comment, or somewhere a box font may be missing:

```
+ - | > v *
```

Never mix the two in one graph.

`▼` and `►` are ambiguous-width — a rare terminal font renders them two columns wide and pushes that line one character right. If the user says the arrows look off, swap those two for `v` and `>` and keep every other Unicode character.

### Arrows are the point

**Every box gets a line drawn into it or out of it.** The only boxes without a line are the ones in the `NO DEPENDENCIES` block.

Never write a shorthand tag in place of a line. `a3` on its own is not an arrow — it is what broke this command before. Draw the line.

The one place a tag helps: a box with a parent far away on the page, where a long line would cross other boxes. Then draw the near parent's line and label the far one `a10` next to the box. Prefer drawing both lines.

### Layout — chains, not levels

Group by **flow**, not by depth. Three kinds of block:

| Block | Holds |
|---|---|
| `NO DEPENDENCIES` | steps with no parent and no child |
| `CHAIN A`, `CHAIN B`, … | one connected run of work, named |
| `JOIN` | a step several chains feed into |

Name each chain for what it does — `CHAIN A ── the hook rewrite`, not `CHAIN A`.

Chains run down the page. Where one step feeds several, fan out sideways.

Worked example, a real 17-step plan:

```
NO DEPENDENCIES ── start any of these now, nothing waits on them
┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ [ ] 1  Drop ||true │ │ [ ] 8  Except doc  │ │ [ ] 14 13 floors   │
│  settings.json:23  │ │  3-inline.md       │ │  checked > 120     │
│  5 min             │ │  30 min            │ │  2 h               │
└────────────────────┘ └────────────────────┘ └────────────────────┘
┌────────────────────┐ ┌────────────────────┐
│ [ ] 15 Print all   │ │ [ ] 16 Name enums  │
│  alembic_env:784   │ │  temporal_type 1,2 │
│  5 min             │ │  10 min            │
└────────────────────┘ └────────────────────┘

CHAIN A ── the hook rewrite
┌────────────────────┐
│ [ ] 2  One scan    │
│  sh:30-39 drop $1  │
│  20 min            │
└──────────┬─────────┘
           │
           ├─────────────────────┬──────────────────────┐
           │                     │                      │
           ▼                     ▼                      ▼
┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ [ ] 3  Del grep -v │ │ [ ] 4  Fix check 6 │ │ [ ] 5  Check 13 v2 │
│  sh:43-44, 628 fls │ │  sh:59 __init__    │ │  #temp in message  │
│  5 min             │ │  20 min            │ │  45 min            │
└────────────────────┘ └────────────────────┘ └──────────┬─────────┘
       ● ends                 ● ends                     │
                                                         ▼
                                              ┌────────────────────┐
                                              │ [ ] 6  Add check14 │
                                              │  .sql in apis/     │
                                              │  30 min            │
                                              └──────────┬─────────┘
                                                         │
                                                         ▼
                                              ┌────────────────────┐
                                              │ [ ] 7  Rewrite md  │
                                              │  14 checks, no arg │
                                              │  30 min            │
                                              └──────────┬─────────┘
                                                         │
                                                         └───────► 17

CHAIN B ── kill the shared package
┌────────────────────┐              ┌────────────────────┐
│ [ ] 9  Restore sql │              │ [ ] 10 Paste 22 py │
│  21 files          │              │  widgets/*/data/   │
│  15 min            │              │  half a day        │
└──────────┬─────────┘              └──────────┬─────────┘
           │                                   │
           ▼                                   │
┌────────────────────┐                         │
│ [ ] 11 Inline 9 gn │                         │
│  data_service:44   │                         │
│  2 h               │                         │
└──────────┬─────────┘                         │
           │                                   │
           └─────────────────┬─────────────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ [ ] 12 Del package │
                  │  77 classes gone   │
                  │  5 min             │
                  └──────────┬─────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │ [ ] 13 pyproject   │
                  │  shared/:124       │
                  │  2 min             │
                  └──────────┬─────────┘
                             │
                             └───────► 17

JOIN
                  ┌────────────────────┐
       7 ────────►│ [ ] 17 Run tiers   │
      13 ────────►│  floor 6 aspose    │
                  │  45 min            │
                  └────────────────────┘

[x] done  [>] now  [ ] next  [!] blocked   ● = chain ends here
Critical path: 10 ─► 12 ─► 13 ─► 17   (about 5 h)
Gate: backend is on `dev`, clean. Never commit on dev — you ask for the branch.
```

Under every graph, three lines: the legend, the critical path with a total time, and any gate.

### Alignment

The arrow must land on the box it points at. Count columns before you draw.

- A box's exit `┬` sits at inner column 11.
- Side-by-side boxes sit at column 0, 23, 46 — one space between them.
- A fan bar's `├` lines up with the parent's exit; each `┬` and `┐` lines up with a child's exit column.

A misaligned arrow is worse than no arrow. If you cannot line it up, stack the boxes instead.

### When it will not fit

- More than 3 boxes fanning out: wrap to a second row of boxes under the first, fed by the same bar.
- A chain deeper than about 10 boxes: cut it and write `└───► continues below` then restart with `CHAIN A (cont.)`.
- Never let a line wrap. A wrapped graph is worse than no graph.

If the plan is a straight line with no parallelism, say so in one line and still draw the boxes and arrows — the user asked for the graph.

## Step 5 — Matrix table

One row per step. Every cell ≤ 30 characters. No semicolon lists inside a cell — if three facets matter, add three columns.

| # | Step | Touches | Depends on | Effort | Status |
|---|---|---|---|---|---|
| 1 | Add tenant_config row | `tenant_config` | — | 5 min | done |
| 2 | Seed dev database | `seed.sql` | — | 10 min | done |
| 3 | Branch on admin URL | `auth/login.py` | 1, 2 | 30 min | now |
| 4 | Screenshot both logins | — | 3 | 10 min | blocked |

Column rules:

- **Touches** — one real file, table, or endpoint. Not a description.
- **Depends on** — step numbers only, or `—`.
- **Effort** — concrete units: `5 min`, `2 h`, `half a day`. Never "some work".
- **Status** — one of `done`, `now`, `next`, `blocked`.

Add columns when the plan needs them (`Owner`, `Risk`, `Verify`). Never widen a cell to fit more.

## Step 6 — Detail, point form

The matrix is an index. The graph is a map. The detail is where the meaning lives — and it is **point form, never paragraphs**.

A wall of prose gets skipped, so the work in it never happens. Five short bullets beat one dense paragraph every time.

### The shape

Header line, then bullets. Same labels every step:

> **2. Re-apply maths** `[ ]` · 45 min · after 1
> - Now: `report_studio.py:622` **adds** returns up — `SUM(CASE WHEN ... THEN ror ELSE 0 END)`
> - Fix: **multiply** them — `EXP(SUM(LOG(1+ror)))-1`
> - Real damage: Allegion shows **+1.67%** for a period it **lost 0.18%**
> - Also `:507`: add `AND opening_value <> 0`, or WEX's **$1,798,325.94** is subtracted twice
> - Skip it: the grid keeps showing wrong numbers

| Bullet | Holds |
|---|---|
| Now: | what the code does today |
| Fix: | what it should do instead |
| Real damage: | a real number or string |
| Skip it: | what stays broken |

Drop any bullet that has nothing real to put in it. Four bullets is fine. Two is fine.

### Hard caps

| Cap | Value |
|---|---|
| Bullets per step | 5 |
| Lines per bullet | 1 |
| Bold per step | 1 or 2 numbers |
| Background prose | none |

### Easy English — this matters most

Write the sentence a reader who has never seen the code still understands. No jargon, no long words where a short one works, no clause stacking.

| Do not write | Write |
|---|---|
| performs arithmetic summation | adds them up |
| the grain diverges | the two queries count different rows |
| returns a read_failed envelope | the panel shows nothing |
| is not propagated downstream | is dropped |
| no-op | changes nothing |

Never explain background. If the reader wants the why, they will ask.

### Two more worked examples

> **1. Rebase onto dev** `[!]` · 30 min · **you run this, I do not switch branches**
> - Do: `git rebase origin/dev`
> - Why: branch is **107 commits behind**
> - Conflicts: `contribution_sql.py`, `contribution_service.py`
> - Skip it: every step below edits SQL that dev already moved to `report_studio.py`

> **9. Narrow the reason code** `[ ]` · 15 min · after 1
> - Now: `contribution_service.py:360` badges a security "cannot compute" if **any one day** has no market value
> - Real case: WEX has **1 bad day out of 350** — and a correct **−21.30%** return
> - So the user sees: a right number, with a "cannot compute" badge on it
> - Fix: its own reason code, or a threshold

If you cannot fill `Real damage:` with something real, you do not understand the step — go read the code, or drop the step and say why.

## Step 7 — Close

One line: the single next action, small enough to start now.

`Next: open auth/login.py:88.`

## Never

- Never change a file, run a build, or start a step. This command shows; it does not do.
- Never draw a step as a bare line of text. Every step is a box.
- Never draw a box with no arrow touching it, unless it sits in `NO DEPENDENCIES`.
- Never write `a3` in place of a line. A tag is not an arrow.
- Never group the graph by `LEVEL 0 / LEVEL 1`. Group it by chain, and connect the chain.
- Never write the detail as paragraphs. Point form only.
- Never mix Unicode and ASCII box characters in one graph.
- Never widen a box or a matrix cell to fit more words. Cut the words.
- Never re-open a decision the user already made. If a step says "add a row to `tenant_config`", that is the design — show it, do not counter-propose.
- Never pad the matrix with rows that are not real work.
- Never replace the graph or the matrix with a bullet list.
- Never draw the graph as mermaid, HTML, or an image. The terminal cannot render them.
