---
name: show-plan
description: "Show the full current plan — nothing summarised, nothing cut — as a goal line, a picture of the real files, tables and screens it touches, a matrix table of every step, and point-form detail per row. Triggers on 'show me the plan', 'show the full plan', 'what's the plan', 'plan with graph and matrix', or /show-plan. Strictly read-only: changes no file, runs no state-changing command."
allowed-tools: Read, Glob, Grep, Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(ls:*), Bash(cat:*)
---

# Show Plan

## Overview

Displays the plan that is already in play. It does not invent one, does not refine one, and does not start executing one.

The output is always the same four blocks, in this order:

1. **Goal** — one sentence.
2. **Graph** — a picture of the real files, tables and screens the plan touches.
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

If the plan has 23 steps, the matrix has 23 rows and the detail has 23 blocks. A long plan is the reason the user asked.

The graph is the exception: it draws the system, not one box per step, so it has as many boxes as the system has parts.

## Step 3 — Goal

One sentence, plain English, no jargon. What is true when the whole plan is done.

Then one line: what is done already, what is left. Real numbers — "4 of 11 steps done".

## Step 4 — Graph

**Draw the system, not the schedule.**

The matrix below already carries the step number, the effort, the status and the order. The graph must not repeat any of them.

What the matrix cannot show is the shape of the thing being changed — which file feeds which, which tables join on what column, what the screen looks like. That is the graph's only job.

Put it in a plain fenced code block. It must render in a terminal, so no mermaid, no HTML, no images — the TUI shows those as raw text.

### The five rules

| Never in a box | Draw instead |
|---|---|
| `30 min`, `2 h` | nothing — matrix has it |
| `[ ] 16 sidebar` | `sidebar.jsx` |
| `sidebar.jsx:66` inside | `+1 nav item` at right |
| fixed-width box | as wide as the real name |
| plain `│` edge | `│ zone_id` |

- **No durations.** Eighteen boxes each carrying `30 min` is eighteen wasted lines, and `Effort` is already a matrix column.
- **Name the real thing.** `sidebar.jsx` can be grepped and opened. `16 sidebar` is the plan talking about itself.
- **Counts go outside the box, on the right.** `12 rows`, `13 pins`, `3 tables / 19 cols`. Inside the box goes the name and nothing else.
- **Box width follows the name.** `dbo.tenant_login_detail` gets a box 25 wide. Never shorten a real name to fit a box.
- **Label the edge.** The join column, the import, the route, the key — `zone_id`, `-r`, `POST /sso/callback`, `sso_encrypt_key`. A bare `│` says only "after", which the matrix already said.

Not everything has to be a box. A plain name with a line off it is often clearer than a box.

### No chains, no levels, no JOIN block

Do not group the graph by `CHAIN A / CHAIN B`, by `LEVEL 0 / LEVEL 1`, or by a `JOIN` block. Execution order is the matrix's `Depends on` column, and drawing it twice is what made the old graph unreadable.

Group by the real area of the system instead, and head each block with what it is: `the SSO database`, `the screen`, `the build step`.

### Three kinds of picture

Draw the ones the plan actually needs. One is usually enough. Three is the most there should ever be.

**1. The system** — what talks to what, and over which column or key.

```
the SSO database

  omrobot db                     aisql-omegasso-dev
  ──────────                     ──────────────────
  omega_env DEV ─── sso_db_* ──► dbo.zone                   1 row
       │                              ▲
       │                              │ zone_id
       │                         dbo.tenant                 12 rows
       │                              ▲
       │ sso_encrypt_key              │ tenant_id
       └─────── unseals ────────► dbo.tenant_login_detail    11 rows
                                  fa_client_secret = Fernet token

  12 tenants, 11 login rows — 104 CWKJH is the one that cannot sign in.
  Three files get you there: db.py:108 twin session · model_sso.py 3 tables /
  19 cols · sso_crypto.py unseals with the DEV key.
```

**2. The screen** — when the plan builds or changes UI, draw it with real data sitting in it.

```
the screen

  ┌──────────────────────────────────────────────────────────────┐
  │  SSO Config                     [ DEV ]         [ ⟳ Refresh ]│
  ├──────────────────────────────────────────────────────────────┤
  │  Zones                                         [ + Add zone ]│
  │  ┌────┬───────┬────────────────────────┬────────┬───────┐    │
  │  │  4 │ zone1 │ https://aidev-omegana… │ active │ ✎  ✕  │    │
  │  └────┴───────┴────────────────────────┴────────┴───────┘    │
  │  Tenants                                     [ + Add tenant ]│
  │  ┌──────┬───────────────┬───────┬──────────────┬───────┐     │
  │  │ -999 │ PIERSIGHT     │ zone1 │ E2D8B4BB-CC… │ ✎  ✕  │     │
  │  │  104 │ CWKJH      ⚠  │ zone1 │ 1F7BEC8A-DE… │ ✎  ✕  │     │
  │  └──────┴───────────────┴───────┴──────────────┴───────┘     │
  └──────────────────────────────────────────────────────────────┘
       ⚠  104 CWKJH is the one tenant with no login row.

  api.js  ─── 12 calls ───►  the page  ───►  login dlg ┐
                                             2 dialogs ┴──►  sidebar.jsx
                                                             ├ Setting
                                                             └ SSO Config ← new
```

Real rows, real ids, real urls — truncated with `…` where they are long. A wireframe full of `foo` / `bar` is worth nothing.

**3. Before and after** — when the plan reshapes something that already exists, put the two side by side.

```
  TODAY                                AFTER
  ├── requirements.txt      0 pins     ├── pyproject.toml  ◀── you edit this
  ├── shared/requirements   9 pins     ├── uv.lock         ◀── pins transitives
  ├── requirements.swagger 13 pins     └── apis/<c>/
  ├── requirements.pytest  16 pins
  └── …11 more                         15 files become 2.
```

### Charset — Unicode is the default

```
┌ ┐ └ ┘ ─ │ ├ ┤ ┬ ┴ ┼ ▼ ► ◀ ← ● ⚠ ✎ ✕ ⟳ ·  …
```

Emoji are not on the list. They are double-width almost everywhere, so they push the rest of the line one column right and every box below them stops lining up.

Use ASCII only when the output is going into a file, a PR comment, or somewhere a box font may be missing:

```
+ - | > v * (!) [/] [x]
```

Never mix the two in one graph.

`▼` `►` `◀` `⚠` `⟳` `✎` `✕` are ambiguous-width — a rare terminal font renders them two columns wide and pushes that line one character right. If the user says the picture looks off, swap them for `v` `>` `<` `(!)` `(r)` `[/]` `[x]` and keep every other Unicode character.

### Under the picture

One line of plain English saying what the picture means, with a real number in it. Then the gate, if there is one.

```
  12 tenants, 11 login rows. 104 CWKJH is the gap.
  Gate: on `feat/zone-infra-change`, discussion mode on — nothing starts yet.
```

No legend. No critical path. No time total. The matrix carries all three.

### Alignment

The arrow must land on the box it points at. Count the columns before you draw. A misaligned arrow is worse than no arrow — if it will not line up, stack the boxes instead.

### When it will not fit

- **Never let a line wrap.** A wrapped picture is worse than no picture. Keep the whole thing under 80 columns.
- **Ten siblings:** draw three and write `└── …7 more` with the count on the right. Do not draw ten boxes.
- **Over about 40 lines:** it is two pictures, not one.

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
- Never put a duration in a box. Effort is a matrix column and nothing else.
- Never put a step number or a status marker in a box. The matrix owns both.
- Never label a box with the plan's own step title. Label it with the real file, table, screen or route.
- Never leave an edge bare when a real column, import, key or route names it.
- Never shorten a real name to fit a fixed box. Widen the box.
- Never group the graph by `CHAIN A / CHAIN B`, by `LEVEL 0 / LEVEL 1`, or by a `JOIN` block.
- Never draw a critical path, a time total, or a status legend under the graph.
- Never draw a wireframe with placeholder data. Real ids, real urls, real codes, or do not draw it.
- Never write the detail as paragraphs. Point form only.
- Never mix Unicode and ASCII box characters in one graph.
- Never widen a matrix cell to fit more words. Cut the words.
- Never re-open a decision the user already made. If a step says "add a row to `tenant_config`", that is the design — show it, do not counter-propose.
- Never pad the matrix with rows that are not real work.
- Never replace the graph or the matrix with a bullet list.
- Never draw the graph as mermaid, HTML, or an image. The terminal cannot render them.
