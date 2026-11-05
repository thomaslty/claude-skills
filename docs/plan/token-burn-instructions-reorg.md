# Token burn: instruction reorg

Status: done except step 19 (waits for each branch to merge `dev`)
Agreed: 2026-11-04, in the token-burn session (`token_burn/`)

## Goal
Every Omega call carries only the instructions it needs, the dev suite stops growing and re-reading one big `conventions.md`, and the token-burn docs and leftover skills are cleaned up.

## Why
- every Omega call, main and every subagent, re-reads 85k–103k chars of instruction files: global `CLAUDE.md` 11k, root `CLAUDE.md` 17k, `.claude/conventions.md` 37–54k, `MEMORY.md` 21k
- the first read under `backend/` adds `backend/CLAUDE.md`, 47k, and 26k of it is one feature's notes
- `conventions.md` comes in through `@.claude/conventions.md` at root `CLAUDE.md:173`, so a frontend reviewer carries "a text column with a CHECK constraint"
- 4 dev-suite agents read `conventions.md` again on top of that: 338k chars of repeat reads in 30 days
- `dev-implementer` carries the 14.9k-token Artifact schema on 11,418 calls, and used it 3 times
- the token-burn docs say the LINK hook is 24.5k tokens per call (it is ~1.3k) and the plugin removal saves 3.9k per call (it saves ~1.3k, the skills list stays at its 30k-char budget)

## System

```
the Omega instruction stack, TODAY                         chars

  every call, main + every subagent
    ~/.claude/CLAUDE.md                                      11k
    CLAUDE.md                                                17k
     └── @.claude/conventions.md                         37–54k
    MEMORY.md                                                21k
  first read under backend/
    backend/CLAUDE.md                                        47k

the Omega instruction stack, AFTER

  every call
    ~/.claude/CLAUDE.md                                      11k
    CLAUDE.md                                                ~7k
    .claude/rules/safety.md                                  ~2k
    .claude/rules/workflow.md                                ~4k
    MEMORY.md                                                ~8k
  when a matching file is read
    .claude/rules/backend.md          ◄── backend/**
    .claude/rules/backend-data.md     ◄── backend/database/**
    .claude/rules/backend-deploy.md   ◄── backend/pipeline/**
    .claude/rules/frontend.md         ◄── frontend/**
    backend/CLAUDE.md                                       ~12k
    backend/shared/repository/ev/CLAUDE.md                   26k
    backend/test/CLAUDE.md                                   +3k
  only when opened
    backend/docs/claude/db-apply.md   ◄── you approve an apply
    backend/docs/claude/incidents.md
```

```
the dev suite (this repo and ~/.claude)

  dev-convention-learner ──► .claude/rules/<area>.md     was conventions.md
  dev-designer ──► dev/<slug>/canvas/project/*.dc.html
                   │ Read
                   ▼
                   dev-implementer                       no Artifact
```

## Decisions

| Decision | Picked |
|---|---|
| Where Omega work lands | `dev`, directly |
| Commits | as you go, small, easy to revert |
| Local dev commands | docker only |
| Root repo branch | `dev` |
| General workflow rules | dev suite, not the repo |
| Dated incident stories | a doc |
| Memory trim | shorten lines, delete nothing |
| `cleanupPeriodDays` | keep 365 |
| Compaction window | stays `auto` (1M) |
| Bash output cap | unchanged |
| Bullets about other repos | out of AIO, kept below |
| Rules file size cap | ~8k chars each |
| Anything removed | moved to a backup |

- the live `~/.claude` copies of `dev-designer.md` and `dev-implementer.md` carry another session's newer edits (`dev-suite-speedup.md`), so each edit here is made in both copies, never by copying a whole file over
- in this repo only files nobody else has open changes in get committed

## Matrix

| # | Step | Repo | Touches | Depends on | Effort |
|---|---|---|---|---|---|
| 1 | Remove taste-pack sources | ~/.agents | `.skill-lock.json` | — | 5 min |
| 2 | Correct token_burn docs | claude-skills | `token_burn/*.md` | — | 20 min |
| 3 | Learner writes rules files | claude-skills | `dev-convention-learner.md` | — | 30 min |
| 4 | Fix learn-conventions text | claude-skills | `learn-conventions.md` | 3 | 10 min |
| 5 | Drop repeat conventions read | claude-skills | `agents/dev-*.md` | — | 15 min |
| 6 | Implementer reads local design | claude-skills | `dev-implementer.md` | — | 15 min |
| 7 | Move general workflow rules | claude-skills | `agents/dev-*.md` | — | 45 min |
| 8 | Same edits in ~/.claude | ~/.claude | `~/.claude/agents/` | 3, 4, 5, 6, 7 | 5 min |
| 9 | Write DB-apply + incident docs | Omega backend | `docs/claude/` | — | 30 min |
| 10 | Trim backend CLAUDE.md intro | Omega backend | `backend/CLAUDE.md` | 9 | 45 min |
| 11 | Move standalone notes | Omega backend | `repository/ev/CLAUDE.md` | — | 20 min |
| 12 | Move testing sections | Omega backend | `test/CLAUDE.md` | — | 10 min |
| 13 | Split conventions into rules | Omega root | `.claude/rules/*.md` | 7 | 1 h |
| 14 | Drop conventions.md + import | Omega root | `CLAUDE.md:173` | 3, 13 | 5 min |
| 15 | Rewrite root CLAUDE.md | Omega root | `CLAUDE.md` | 9, 13 | 45 min |
| 16 | Bump backend gitlink | Omega root | `backend` gitlink | 10, 11, 12 | 5 min |
| 17 | Trim Omega MEMORY.md | memory | `MEMORY.md` | — | 30 min |
| 18 | Measure a fresh Omega session | — | first request in log | 8, 14–17 | 15 min |
| 19 | Re-file worktree bullets | Omega root | 3 feature branches | 14 | 20 min each |

## Steps
- [x] 1. Move the 11 unused taste-pack folders out of `~/.agents/skills` into `~/.claude-token-burn-backup-2026-11-04/`, drop their lock entries — verify: `ls ~/.agents/skills` lists 6
- [x] 2. `token_burn/`: fix the LINK and removal numbers, drop the ruled-out levers — verify: read
- [x] 3. `dev-convention-learner.md`: write `.claude/rules/<area>.md` with `paths`, no import, ~8k cap, file a leftover `conventions.md` — verify: read
- [x] 4. `learn-conventions.md` and `help.md`: say `.claude/rules/` — verify: `grep -rn 'conventions.md' commands/` finds only the leftover note
- [x] 5. implementer, designer, explorer, researcher: read conventions only for other repos — verify: read
- [x] 6. `dev-implementer.md`: `disallowedTools: Artifact`, read the design from `dev/<slug>/canvas/project/` — verify: read
- [x] 7. the general Omega workflow bullets go to the dev-suite phase that owns them — verify: each one found in its agent
- [x] 8. the same edits in `~/.claude/agents/` and `~/.claude/commands/dev/` — verify: `grep` finds each change in both copies
- [x] 9. `backend/docs/claude/db-apply.md` and `incidents.md` — verify: read
- [x] 10. `backend/CLAUDE.md`: intro without the repeats, one line per coding-style link — verify: `wc -c`
- [x] 11. `backend/shared/repository/ev/CLAUDE.md`: Standalone zone, Reads, Writes, Flow Studio — verify: gone from `backend/CLAUDE.md`
- [x] 12. `backend/test/CLAUDE.md`: Test taxonomy and Testing procedure — verify: gone from `backend/CLAUDE.md`
- [x] 13. `.claude/rules/`: safety, workflow, backend, backend-data, backend-deploy, frontend — verify: all 91 bullets accounted for
- [x] 14. delete `.claude/conventions.md` and `CLAUDE.md:173` — verify: `grep -rn conventions.md CLAUDE.md` finds nothing
- [x] 15. root `CLAUDE.md`: docker only, root on `dev`, no repeats — verify: `wc -c` near 7k
- [x] 16. root repo points at the new backend commit — verify: `git ls-tree HEAD backend`
- [x] 17. `MEMORY.md`: one short line per memory, status moved into the memory file — verify: `wc -c` near 8k, 120 lines still
- [x] 18. a fresh Omega session's first request, split the same way — verify: instruction files ~32k chars
- [ ] 19. each feature worktree: extra bullets filed when it merges `dev`, by the learner's step 1 on its next phase — verify: no `conventions.md` left on the branch

## Detail

**1. Remove taste-pack sources** · 5 min
- Now: 11 unused folders in `~/.agents/skills`, nothing links to them
- Fix: copy `.skill-lock.json` to the backup, move the 11 folders there, delete their 11 lock entries
- Keep: `design-taste-frontend`, `redesign-existing-projects` and the 3 Orca skills

**2. Correct token_burn docs** · 20 min
- Now: they say the LINK hook costs **24.5k** tokens per call, it costs ~1.3k
- Now: they say the removal saves 3.9k per call, it saves ~**1.3k**
- Fix: drop compact at 300k, shorter implementer runs, smaller Bash output and the LINK hook row
- Fix: list the Omega reorg and `skillListingBudgetFraction` as the levers left

**3. Learner writes rules files** · 30 min
- Now: `dev-convention-learner.md:9` writes only `.claude/conventions.md`, and its step 5 adds the `@` import
- Fix: write `.claude/rules/<area>.md` with `paths:` frontmatter, never the import
- Fix: ~8k chars per file, replace an old bullet instead of only appending
- Fix: a `conventions.md` still there, like after a branch merges `dev`, gets filed into the rules files and removed
- Real damage: `conventions.md` reached **54,351** chars in `feat-crypto-with-pe`

**4. Fix learn-conventions text** · 10 min · after 3
- Now: `learn-conventions.md:3` says it merges into `.claude/conventions.md`, "imported from CLAUDE.md"
- Fix: say `.claude/rules/`, and the same in the `help.md` row

**5. Drop repeat conventions read** · 15 min
- Now: `dev-implementer.md:30`, `dev-designer.md:23`, `dev-explorer.md:33`, `dev-researcher.md:39` read it on top of the automatic load
- Real damage: **338k** chars of repeat reads in 30 days, 16 by the implementer
- Fix: read the rules only of other repos under `## Repos`, the current repo's load on their own

**6. Implementer reads local design** · 15 min
- Now: the **14.9k**-token Artifact schema on every implementer call, used 3 times in 30 days
- Fix: `disallowedTools: Artifact`, read `dev/<slug>/canvas/project/*.dc.html` with Read
- Real case: 2026-10-28 it read `Rates-year-range.dc.html` from the canvas, the designer had written it locally (`dev-designer.md:265`)
- Watch: a design you edited on the canvas after publish is not in the local copy

**7. Move general workflow rules** · 45 min
- Now: about 18 of the 30 `## Workflow` bullets in Omega's conventions are about working with you, not Omega
- Fix: each one goes to the phase that owns it, like "link each changed file" to `dev-reviewer.md`
- Fix: the commit rule is "commit as you go, in small batches, easy to revert", "only when Thomas says so" goes

**8. Same edits in ~/.claude** · 5 min · after 3–7
- Now: `~/.claude` is the live copy, and its `dev-designer.md` is ahead of this repo
- Fix: the same small edit in both copies, never a whole-file copy

**9. Write DB-apply + incident docs** · 30 min
- Now: the 11-row approval protocol (~3.5k chars) is in both root and `backend/CLAUDE.md`
- Fix: one copy in `backend/docs/claude/db-apply.md`, read when you approve a named apply
- Fix: the dated stories, like "(2026-07-27: … re-ran a 187-batch plan…)", go to `backend/docs/claude/incidents.md`
- Why backend: a backend-only clone never sees the root repo

**10. Trim backend CLAUDE.md intro** · 45 min · after 9
- Now: the intro is **13,058** chars of 🚨 rules
- Fix: drop the TABLE RULE, "no-op" and "over engineer" copies, they load from the global file and the root
- Fix: rules that point at `docs/coding-style/*` keep one line and the link

**11. Move standalone notes** · 20 min
- Now: `## Standalone zone`, `### Reads`, `### Writes`, `### Flow Studio` are **26,154** chars of `backend/CLAUDE.md`
- Fix: move them to `backend/shared/repository/ev/CLAUDE.md`, it loads when that code is read

**12. Move testing sections** · 10 min
- Now: `## Test taxonomy` and `## Testing procedure` (3,225 chars) in `backend/CLAUDE.md`
- Fix: add them to `backend/test/CLAUDE.md`

**13. Split conventions into rules** · 1 h · after 7
- Now: 91 bullets, **36,527** chars, loaded on every call
- Fix: `backend.md` `paths: backend/**`, `frontend.md` `paths: frontend/**`
- Fix: `backend-data.md` for `backend/database/**` and `backend/shared/entity/**`, `backend-deploy.md` for `backend/pipeline/**` and `backend/deployment/**`
- Fix: `safety.md` and `workflow.md` with no `paths`, always loaded, Omega's own rules only

**14. Drop conventions.md + import** · 5 min · after 3, 13
- Fix: delete `CLAUDE.md:173` and the file once step 13 holds every bullet
- Check: the **91** bullets are filed, moved to the suite, or kept below

**15. Rewrite root CLAUDE.md** · 45 min · after 9, 13
- Now: **16,599** chars, 3 contradictions
- Fix: docker only, drop the uvicorn/npm table, ports `:4209` and `:8888`
- Fix: root on `dev`, fix the "root sits on `master`" row
- Fix: no TABLE RULE or "over engineer" copy, DB rules in `safety.md` with the step 9 link

**16. Bump backend gitlink** · 5 min · after 10–12
- Fix: `git add backend && git commit` in the root after the backend commits

**17. Trim Omega MEMORY.md** · 30 min
- Now: 120 lines, **20,871** chars, the longest line 423 chars
- Fix: each line is the link plus a short hook, the old line goes into its memory file
- Nothing deleted: you left it to me, and a status line costs less than a lost lesson

**18. Measure a fresh Omega session** · 15 min · after 8, 14–17
- Do: one `claude -p` session in the main checkout, with one subagent, then split its first requests from the log
- Pass: instruction files ~32k chars, and no `conventions.md` in the subagent's first request

**19. Re-file worktree bullets** · blocked · after 14
- Now: `feat-crypto-with-pe` 54,351 chars, `feat-dealer-request-round2` 52,691, `fix-omega-entity-deployment` 39,923, vs 36,527 on `dev`
- Fix: when each merges `dev`, the next learner run files its leftover `conventions.md` (step 3)

## Not filed in AIO
Bullets from `conventions.md` about other repos, kept here word for word for Omega.Sync and Omega.Entity:

- An OM Robot "<X> Management" sidebar group splits into two menu items: the catalogue page (add, update, delete) and a "Relationship" page for the per-tenant ticks, like Module Management in `OM.Robot/frontend/components/app-sidebar.jsx:68` and Import Management (`/import-management/import-type`, `/import-management/relation`) — seen 2, human, 2026-10-21
- An `ev` table, even a tool's own bookkeeping table, is made by an Omega.Entity alembic revision, never by a `.sql` file in the tool's repo; a repo that needs the guard gets a `CLAUDE.md` line and one check script that both a Claude `PreToolUse` hook and `.githooks/pre-commit` run, like `ev.sync_status` from Omega.Entity `0008` replacing Omega.Sync `scripts/sql/ev_sync_status.sql` — seen 1, human, 2026-10-26
- Omega.Sync code lives in `omega_sync/`: commands in `cli/`, shared code in `services/`, settings in one `config.py`; table lists go in `tables/` and tests in `tests/`, and each command is a `[project.scripts]` entry run as `uv run <name>`, like the layout in step 23 of `plan/zone5-standalone-setup/plan.md` — seen 1, human, 2026-10-26
- A table set Omega.Sync reads is a committed `tables/<name>.txt`: a comment header saying where it came from, then one table per line, parents first, like `dev/zone5-standalone-setup/sync/db_sync_syncdb_tables.txt` and Omega.Sync `scripts/db_sync_core_tables.txt` — seen 3, human, 2026-10-26 (was: `scripts/db_sync_<name>_tables.txt`; Thomas moved the lists to `tables/`)
- A script's file name says what it does, verb first, and its `[project.scripts]` command matches it, like `configure_fabric_mirror_table_setting.py` / `uv run configure-fabric-mirror-table-setting`, which writes the Fabric mirror's table list; a name that only names a thing, like Jacob's `fabric_mirror_tables.py`, gets renamed — seen 1, human, 2026-10-26

## Progress
- step 1: 11 folders moved to `~/.claude-token-burn-backup-2026-11-04/agents-skills/`, 11 lock entries dropped — `ls ~/.agents/skills` lists 6
- step 2: LINK hook 1.3k, removal ~1.3k per call, ruled-out levers listed — claude-skills `f8132a1`
- steps 3–8: learner writes `.claude/rules/`, 4 agents stop the repeat read, implementer has no Artifact and commits as it builds, 11 workflow bullets placed in the designer, reviewer and `full-dev-cycle.md`; 8 more were already covered (`1-design.md:11`, `dev-designer.md:201`, `3-review.md:30`, …) — claude-skills `53d7b7d`; the same edits are in `~/.claude`, made in place because another session has newer edits there
- step 7: nothing new went to `~/.claude/CLAUDE.md`: easy English and terminal only were already there or in the suite
- steps 9–12: backend `271c19ca2` (docs/claude) and `702c22c64`; `backend/CLAUDE.md` 47,348 → 12,837 chars, standalone notes in `shared/repository/ev/CLAUDE.md`, Test taxonomy was already in `test/CLAUDE.md`
- steps 13–15: root `d33654f`, `42d73dc`, `22f7076`; 67 bullets in 7 rules files, 19 to the suite, 5 kept below; root `CLAUDE.md` 16,599 → 7,010 chars
- step 16: root `f080f1e`, backend gitlink at `702c22c6`
- step 17: `MEMORY.md` 20,871 → 12,486 chars, 120 lines, longest 154; 2 memory files got their old index text; backup in `~/.claude-token-burn-backup-2026-11-04/omega-memory/`
- step 18: fresh session `71bd8c2a` in the main checkout: 35,216 chars of instruction files on the first request (was 85k–103k), no `conventions.md`; its Explore subagent loads none
- step 19: not run on 2026-11-04, on purpose. Each of the 3 worktrees had a live Claude session (pids 28609, 92090, 14784), 2 with uncommitted `conventions.md` edits, and the branches hold rules for code `dev` does not have yet, like "In a standalone zone every `ev` read and write goes through the omega-entity ORM classes" on `fix/omega-entity-deployment`, which contradicts the `<Name>StandaloneEv` twins in `backend/shared/repository/ev/CLAUDE.md` on `dev`. Branch-only bullets then: crypto 30 (+18 updated), dealer-round2 27 (+16), entity 13 (+5). At each merge, keep the branch's `conventions.md` in the conflict; the learner files it and removes it.
