# Dev suite speed-up

Status: approved
Agreed: 2026-11-04, in the offload-to-localLLM session

## Goal
The dev suite picks effort, review depth and design size from how risky the ticket is, so a small ticket goes from about 61 minutes to about 30 without missing the bugs the offload test found.

## Why
The offload test (`test/offload-to-localLLM/`) took 162 minutes for a Snake game and a 145-line server.

- 79 of the 162 minutes was the review loop, 49 of them qwen pre-passes that fixed nothing
- every agent ran at `xhigh` (`~/.claude/settings.json:225`), and 60-73% of their output was hidden thinking
- 16 lens reviews cost 10.6M tokens for 4 different bugs; correctness and feature reported the same bug every time
- the designer wrote a 690-line plan, and v4's builder wrote 77.6 KB for 15.6 KB of code
- tools took only 3.1 of the builder's 14.7 minutes: the time is what gets written and thought

## System

```
the dev suite, after

  <repo>/.claude/risky.md   drafted by dev-designer when missing
     |
     +-- read by --> 1-design.md --- effort ---> dev-designer.md
     |                                           + Risk column
     |
     +-- read by --> 2-implement.md -- steps: -> dev-implementer.md
     |                                 effort    risky / rest / join
     |
     +-- read by --> 3-review.md ---- effort --> dev-reviewer.md
     |                 |                         all 4 lenses
     |                 +-- risky hit ----------> dev-reviewer.md
     |                 |                         security, xhigh
     |                 +-- re-review ----------> changes.py diff
     |
     +-- read by --> offload-to-localLLM.md ---> omp + qwen
                       parallel, report only     offload.py
                                                 no git credentials
                                                    |
                                    snapshot, diff  |
                                    changes.py <----+

  full-dev-cycle.md   ## Effort table, one learner at the end
```

```
agents per ticket

  TODAY (test v4)                     AFTER
  dev-researcher            2         dev-researcher        0-2
  dev-designer              1         dev-designer            1
  dev-implementer           2         dev-implementer       2-4
  dev-reviewer              8         dev-reviewer          2-3
  dev-convention-learner    3         dev-convention-learner  1
  ---------------------------         ---------------------------
                           16                               6-11
```

## Decisions
| Question | Picked |
|---|---|
| Review | 1 reviewer + risk-triggered security pass |
| Re-review | only the fix diff, once |
| qwen review pre-pass | parallel, report only, round 1 |
| qwen items timing | print Claude's findings at once |
| Small ticket | the plan is the spec |
| Small-ticket gate | rules set a floor, only move up |
| Effort | high, xhigh on risk |
| Build split | risky step alone if separable |
| Risk file | `.claude/risky.md`, every phase |
| Sandbox | none, credentials stripped instead |

## Matrix

| # | Step | Touches | Depends on | Effort |
|---|---|---|---|---|
| 1 | Rename to risky.md | `offload.py:44` | — | 10 min |
| 2 | Shared snapshot + diff | `scripts/dev/changes.py` | 1 | 30 min |
| 3 | Draft risky.md when missing | `dev-designer.md:69` | 1 | 15 min |
| 4 | Risk column in the Matrix | `dev-designer.md:163` | 3 | 10 min |
| 5 | Plan links, never copies | `dev-designer.md:140` | — | 20 min |
| 6 | One step per file | `dev-designer.md:168` | — | 10 min |
| 7 | Small-ticket path | `1-design.md:38` | 3 | 20 min |
| 8 | Effort table | `full-dev-cycle.md:23` | — | 20 min |
| 9 | Designer + researcher effort | `1-design.md:26` | 7, 8 | 10 min |
| 10 | Plan is the spec, small | `development-guideline.md:12` | 7 | 10 min |
| 11 | Skip OpenSpec, small path | `dev-implementer.md:38` | 10 | 15 min |
| 12 | Tick once | `dev-implementer.md:79` | — | 10 min |
| 13 | Walk only untested checks | `dev-implementer.md:83` | — | 15 min |
| 14 | Risk split build | `2-implement.md:37` | 4, 8 | 30 min |
| 15 | `steps:` input | `dev-implementer.md:16` | 14 | 15 min |
| 16 | Fix reruns only its checks | `dev-implementer.md:87` | — | 10 min |
| 17 | One reviewer + security pass | `3-review.md:18` | 1, 8 | 30 min |
| 18 | Reviewer runs all lenses | `dev-reviewer.md:30` | 17 | 15 min |
| 19 | Re-review the fix diff only | `full-dev-cycle.md:28` | 2, 17 | 20 min |
| 20 | qwen pre-pass in parallel | `offload-to-localLLM.md:130` | 17 | 20 min |
| 21 | qwen stops its processes | `offload-worker-rules.md:16` | — | 5 min |
| 22 | No offload under ~300 lines | `offload-to-localLLM.md:35` | — | 10 min |
| 23 | One learner, at the end | `full-dev-cycle.md:56` | — | 15 min |
| 24 | Stops hold under /goal | `full-dev-cycle.md:25` | — | 5 min |
| 25 | Same effort table | `parallel-development.md:58` | 8 | 5 min |
| 26 | Copy to the archive | `claude-skills/` | 1–25, 28, 29 | 10 min |
| 27 | Timed small-ticket run | `test/` | 26 | 45 min |
| 28 | Run qwen without git credentials | `offload.py` `cmd.sh` | — | 10 min |
| 29 | Detect a push after the run | `offload.py:133` | 2 | 10 min |

Every file is under `~/.claude`; step 26 copies them here.

## Steps
- [x] 1. Rename the risk file to `.claude/risky.md` in `offload.py`, `offload-to-localLLM.md` and the `2-full-cycle` fixture — verify: `grep -rn offload-risky ~/.claude` finds nothing
- [x] 2. Move `snapshot`, `changes` and `diff` out of `offload.py` into `scripts/dev/changes.py`, and import them back — verify: a snapshot, an edit, then `changes.py diff` shows only that edit; `offload.py check` on the old runs still works
- [x] 3. `dev-designer.md`: a repo with no `.claude/risky.md` gets one drafted, shown at the design stop — verify: read
- [x] 4. `dev-designer.md`: the Matrix gets a `Risk` column, `high` when a step hits `risky.md` — verify: read
- [x] 5. `dev-designer.md`: `## Research` links the research files, `## Code structure` lists names and signatures only — verify: read
- [x] 6. `dev-designer.md`: one step per file, tests and code together — verify: read
- [x] 7. `1-design.md`: small-ticket path, rules set the floor, the designer may move it up — verify: read
- [x] 8. `full-dev-cycle.md`: `## Effort` table — verify: read
- [x] 9. `1-design.md`: designer and researcher spawns pass effort from the table — verify: read
- [x] 10. `development-guideline.md`: on the small path the plan is the spec — verify: read
- [x] 11. `dev-implementer.md` and `2-implement.md`: no `OpenSpec:` line means no OpenSpec change, and no respawn for it — verify: read
- [x] 12. `dev-implementer.md`: tick once per step, `tasks.md` at the end — verify: read
- [x] 13. `dev-implementer.md`: walk only the Verification checks no passing test covers — verify: read
- [x] 14. `2-implement.md`: risk split when separable, otherwise the whole build at xhigh — verify: read
- [x] 15. `dev-implementer.md`: `steps:` input — verify: read
- [x] 16. `dev-implementer.md`: a fix reruns the suite and only its own checks — verify: read
- [x] 17. `3-review.md`: one reviewer, a security pass on a `risky.md` hit, completeness by script — verify: read
- [x] 18. `dev-reviewer.md`: `lens: all` — verify: read
- [x] 19. `full-dev-cycle.md` and `3-review.md`: re-review reads only the fix diff, once — verify: read
- [x] 20. `offload-to-localLLM.md`: qwen pre-pass in parallel, report only, round 1, 10-minute cap — verify: read
- [x] 21. `offload-worker-rules.md`: stop every process you start — verify: read
- [x] 22. `offload-to-localLLM.md`: under ~300 lines, run on Claude and say why — verify: read
- [x] 23. `full-dev-cycle.md` and the phase commands: one learner at the end inside the cycle — verify: read
- [x] 24. `full-dev-cycle.md`: a `/goal` never answers for the user — verify: read
- [x] 25. `parallel-development.md`: points at the effort table — verify: read
- [x] 26. Copy every changed file to this repo — verify: `cmp` each pair
- [x] 27. Run the original Snake prompt through `/dev:full-dev-cycle` in `test/dev-suite-speedup/` — verify: design to re-review in about 30 minutes
- [x] 28. `offload.py`: omp runs with no git credentials — verify: a push from inside a run fails
- [x] 29. `offload.py`: the snapshot keeps the remote refs, and `check` flags a push — verify: a moved remote ref shows `PUSHED`

## Detail

**1. Rename to risky.md** · 10 min
- Now: `offload.py:44` reads `.claude/offload-risky.md`, and only the offload skill uses it
- Fix: `.claude/risky.md`, also at `offload.py:20`, `:107`, `offload-to-localLLM.md:94` and the `2-full-cycle` test fixture
- Real case: no repo under `toogood/git/ai/` has the old file, so nothing else has to move

**2. Shared snapshot + diff** · 30 min · after 1
- Now: `snapshot()` at `offload.py:133` and `cmd_diff()` at `:370` only work for qwen runs
- Fix: move them into `scripts/dev/changes.py` with `snapshot <dir>` and `diff <dir>`, and `offload.py` imports it
- Why: re-review needs what the fix changed, and nothing is committed
- Skip it: round 2 re-reads all 21 files, like the offload test

**3. Draft risky.md when missing** · 15 min · after 1
- Now: a repo with no file makes offload's deep pass run every time
- Fix: the designer drafts it from the repo's auth, cache, lock, money and migration code, and shows it at the design stop
- Real case: Omega.Next.AIO's draft starts from paths like `cache_helper.py:29`

**4. Risk column in the Matrix** · 10 min · after 3
- Fix: a Matrix row gets `Risk: high` when its files or code patterns hit `risky.md`
- Real case: test v4's steps 3 and 5 (`leaderboard_server.py`) are `high`, steps 7 and 10 are not
- Read by steps 9, 14 and 17

**5. Plan links, never copies** · 20 min
- Now: `dev-designer.md:39` and `:51` copy the research into `## Research`, 96 lines in test v4
- Fix: one link per research file, and `## Code structure` lists names and signatures only (it was 182 lines)
- Why: about 15 agents read the plan

**6. One step per file** · 10 min
- Now: test v4 had 11 steps for 2 files, tests and code as separate steps
- Fix: one step per file with its tests and code; TDD still happens inside the step

**7. Small-ticket path** · 20 min · after 3
- Now: `1-design.md:50` sends every unexplored text ticket to researchers and a full design
- Fix: one repo, no database, no outside API, no new web screen and no `risky.md` hit: no researchers, designer at medium, short plan
- Dynamic: the designer can report it is bigger than it looks and move up to the full path, never down
- Real damage: 4.6 min of research and 15.4 min of design for Snake and a 145-line server

**8. Effort table** · 20 min
- Now: nothing sets effort, so `settings.json:225` runs every agent at `xhigh`
- Fix: `## Effort` in `full-dev-cycle.md`: high by default, xhigh on risk, cross-repo or a round-2 fix, medium for a small design and researchers, low for the learner, qwen always xhigh
- `settings.json` is not touched

**9. Designer + researcher effort** · 10 min · after 7, 8
- Now: `1-design.md:26` passes `effort: medium` only for changes and answers
- Fix: the first designer spawn picks from the table; researchers run at medium

**10. Plan is the spec, small** · 10 min · after 7
- Now: `development-guideline.md:12` says every change starts as an OpenSpec proposal
- Fix: on the small-ticket path the plan is the spec
- Real damage: 20.6 KB of OpenSpec files repeating the plan in test v4

**11. Skip OpenSpec, small path** · 15 min · after 10
- Now: `dev-implementer.md:29` says never skip it, and `:38` writes the change before code
- Fix: a plan with no `OpenSpec:` line on the small path skips that section, and `2-implement.md` step 4 skips its `openspec status` check
- Skip it: 2-implement respawns the implementer for a missing spec, forever

**12. Tick once** · 10 min
- Now: `dev-implementer.md:79` ticks the plan and `tasks.md`, plus a Progress line: 25 edits in test v4
- Fix: one Edit per step for the plan tick and Progress; `tasks.md` is ticked once at the end

**13. Walk only untested checks** · 15 min
- Now: `:83` walks all of `## Verification` by hand: 12 checks, 20 evidence files
- Fix: a check with a passing test counts as its evidence; walk only the rest
- Real case: 10 of the 12 were tests already, like check 6 = `test_ctrl_c_quits_cleanly`
- Frontend pages still get chrome-devtools screenshots

**14. Risk split build** · 30 min · after 4, 8
- Now: `2-implement.md:37` splits only by repo
- Fix: separable risky steps (no shared file, waiting only through `## Contract`) get an xhigh implementer, the rest a high one, then a join; not separable means xhigh for the whole build
- Real case: test v4 runs steps 2-5 at xhigh, 6-10 at high, 11 as the join

**15. `steps:` input** · 15 min · after 14
- Now: `dev-implementer.md:16` takes `repo` to pick its steps
- Fix: it also takes `steps: 2-5`, running only its own tests and leaving Verification to the join

**16. Fix reruns only its checks** · 10 min
- Now: `:87` reruns all of `## Verification`: 11.4 min and 19 evidence files for about 30 lines in test v4
- Fix: the full test suite, plus only the checks for the functions the fix changed

**17. One reviewer + security pass** · 30 min · after 1, 8
- Now: `3-review.md:18` spawns 4 lenses every time: 10.6M tokens for 4 unique bugs
- Fix: 1 reviewer at high with all lenses, plus 1 security reviewer at xhigh when the diff hits `risky.md`; completeness by `plan-status.py` and `openspec status`
- Real case: a Snake-only diff gets 1 agent, the server diff 2

**18. Reviewer runs all lenses** · 15 min · after 17
- Now: `dev-reviewer.md:30` takes one `lens`
- Fix: `lens: all` checks correctness, feature and completeness in one read; `lens: security` stays for the risk pass

**19. Re-review the fix diff only** · 20 min · after 2, 17
- Now: `full-dev-cycle.md:28` allows 2 fix rounds, each a full re-review
- Fix: `changes.py snapshot` before the fixes, then re-review only `changes.py diff`, once
- Real case: both round-2 bugs were in fix lines, `leaderboard_server.py:70` and `snake.py:187`

**20. qwen pre-pass in parallel** · 20 min · after 17
- Now: `offload-to-localLLM.md:130` blocks the reviewers and lets qwen edit code
- Fix: it starts with Claude's reviewer, 10-minute cap, never edits, round 1 only; Claude's findings print at once, and qwen's unconfirmed `qwen-<n>` items are added before the reply
- Real damage: 47.5 min of waiting, 0 files fixed

**21. qwen stops its processes** · 5 min
- Fix: `offload-worker-rules.md`: stop every process you start before you write the report
- Real damage: a round-2 `snake.py` ran 65 min after qwen was stopped

**22. No offload under ~300 lines** · 10 min
- Fix: under about 300 lines of code per repo in the plan, the skill says why and runs on Claude
- Real case: test 1 took 8.2 min with offload against 0.7 for Claude; test v2's build 25.2 against 14.7
- 300 is a guess

**23. One learner, at the end** · 15 min
- Now: a learner after design (`1-design.md:28`), implement (`2-implement.md:34`) and review (`3-review.md:33`)
- Fix: inside the cycle, one learner at low effort in the background at When done; a command run alone keeps its own

**24. Stops hold under /goal** · 5 min
- Now: rules 1 and 2 at `full-dev-cycle.md:25` do not mention `/goal`, and the offload test wrote "fix all" as the user's reply
- Fix: a `/goal` never answers for the user; a stop is passed only when the user's own message names it
- Real damage: 3 rules marked `human` in `2-full-cycle/.claude/conventions.md`, from Claude's words

**25. Same effort table** · 5 min · after 8
- Now: `parallel-development.md:58` says same effort as the main session, do not downgrade
- Fix: point at the effort table

**26. Copy to the archive** · 10 min · after 1-25, 28, 29
- Real copies, no symlinks; `installPath` stays under `~/.claude`

**27. Timed small-ticket run** · 45 min · after 26
- Run the original Snake prompt through `/dev:full-dev-cycle` in `test/dev-suite-speedup/`
- Pass: design to re-review in about 30 min (it was about 61), with the same bugs caught
- The user's `/goal` "execute the plan autonomously" is the go for this run's stops; no reply is written in the user's name

**28. Run qwen without git credentials** · 10 min
- Now: `cmd.sh` starts omp with the full environment, so qwen could push through `python3 -c "subprocess.run(['git','push'])"`
- Fix: `env -u SSH_AUTH_SOCK -u GIT_ASKPASS GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0` in front of omp, for that run only

**29. Detect a push after the run** · 10 min · after 2
- Now: `check` sees a changed branch, HEAD or stash, but not a push
- Fix: the snapshot keeps `git for-each-ref refs/remotes`, and `check` flags a change as `PUSHED`

## Progress
- step 1: `.claude/risky.md` in `offload.py`, `offload-to-localLLM.md` and the `2-full-cycle` fixture — `grep -rn offload-risky ~/.claude` finds nothing
- step 2: `scripts/dev/changes.py` (snapshot, list, diff); `offload.py` imports it — a snapshot, one edit and one new file: `list` shows `modified a.txt`, `added new.txt`, and the file that was dirty before the snapshot is not counted; old runs' `offload.py check` still works
- steps 3-6: `dev-designer.md` gets `## Small ticket`, `## Risk file`, `Size:`, the `Risk` column, research as links, signatures only, one step per file
- steps 7, 9: `1-design.md` small path at medium, the first designer's effort from the table, `SIZE: full` moves it up, the drafted risk file is printed at the stop
- step 8: `## Effort` and `## Risk` in `full-dev-cycle.md`
- steps 10-11: `Size: small` plans skip OpenSpec in the guideline, `dev-implementer.md` and `2-implement.md` step 4
- steps 12-13, 15-16: `dev-implementer.md` ticks once, walks only untested checks, takes `steps:`, and a fix reruns only its checks
- step 14: `## Risk split` in `2-implement.md`
- steps 17-19: `3-review.md` rewritten: completeness by script, one `lens: all` reviewer, a security pass at xhigh when risky, re-review on the fix diff once; `dev-reviewer.md` takes `lens: all` and `diff:`; `review-findings.py` knows `qwen` — a merge of `all.json` and `qwen.json` lists both
- step 20: the qwen pre-pass runs next to the reviewers, report only, 10-minute cap; `offload.py restore --all`
- step 21: `offload-worker-rules.md`: stop every process you start, no git or gh through another program — a real qwen run reported "no processes started"
- step 22: under ~300 lines the offload skill runs on Claude and says why
- step 23: one learner at `effort: low` at the end of the cycle, `phase: cycle`
- step 24: rule 2 in `full-dev-cycle.md`: a `/goal` never answers a stop
- step 25: `parallel-development.md` points at the effort table
- step 26: 17 files copied here, `cmp` same for every one, 0 symlinks
- step 28: omp starts with no git credentials — inside, `credential.helper` is empty (outside: `osxkeychain`) and `SSH_AUTH_SOCK` is empty; a real qwen run still finished: `RESULT: PASS`
- step 29: snapshots keep the remote refs — a push, then HEAD moved back: `HEAD: ok`, `REMOTES: PUSHED refs/remotes/origin/master`, `RESULT: FAIL`
- step 27 note: a dev-designer started in this session ran the definition loaded when the session began, not the edited file (its transcript has "a short real snippet", not "No body and no snippet"). Agents pick up edits to `~/.claude/agents/` only in a new session. For this run, each agent is told to read its own current file first; the 70-second design from the old definition was thrown away
- step 27 fix: the other session's "dev-implementer commits as it builds" (53d7b7d) broke two things this plan relies on. `changes.py` compared a clean file with today's HEAD, so a fix committed after the snapshot vanished from the diff: it now uses the snapshot's own commit (a commit after the snapshot still shows `-two +TWO`). And `3-review`'s fallback base, `master`, is the last build commit in a repo with no remote: `2-implement` now writes `Base:` under the plan's `Ticket:` line before the build, and `3-review` uses it
- step 27: `test/dev-suite-speedup/`, the original Snake prompt through `/dev:full-dev-cycle`: design to clean review in **8 min 48 s**, against about 61 min for test v4's design to re-review. The ticket is smaller than v4's (no leaderboard server), so not all of that is the suite. Like for like: the plan went from 209 lines with the old designer to 85 (`Size: small`, 3 steps, `risky.md` drafted); review went from 4 lenses, 5 min and 2.5M tokens to 1 reviewer, 0.8 min and 123k; 4 agents in all against 16. Agents used 1.1M tokens and 28.5k output, against about 27.8M and 408k for test v4. The bugs the old builds had are gone: holding Right reaches the wall in 2.7 s, the same as no keys; a resize, Ctrl-C, q and the wall all exit 0 with no traceback; 12 unit tests pass. The review found 0 T0, so there was no fix round and no re-review. The stops were passed on this plan step, the user's own `/goal`; no reply was written in the user's name, and the learner got no feedback
