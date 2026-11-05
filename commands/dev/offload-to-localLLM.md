---
name: offload-to-localLLM
description: "Hand the coding to the local model (qwen through omp) while Claude stays the driver: Claude writes the brief, the tests, the specs and the look, qwen writes the code in the background, and Claude checks every run before anything counts. Use it alone with a task, or next to another /dev skill, like '/dev:2-implement + /dev:offload-to-localLLM' or '/dev:full-dev-cycle + /dev:offload-to-localLLM'. Triggers on /dev:offload-to-localLLM, 'offload to qwen', 'let the local model code it'."
argument-hint: "[task text | plan/<slug>/plan.md]"
---

# Offload to the local model

Claude is the driver and qwen is the worker. qwen is whatever omp's `default` model is, `vllm/qwen3.8-flash-next` today, always at `--thinking xhigh`. It writes code and nothing else. Specs, tests and instructions are Claude's, because a bug in the code gets caught and a bug in the spec does not.

The tool is `python3 ~/.claude/scripts/dev/offload.py`. Run it with no command for its help.

## Who does what

| Task | qwen | Claude |
|---|---|---|
| Explore, plan, root cause | — | all of it |
| OpenSpec change | — | all of it |
| Tests, every kind | — | all of it |
| Briefs | — | all of it |
| Docs, README | — | all of it |
| Migrations, RLS SQL | — | all of it |
| Backend code | writes it | reads the diff |
| Frontend look | — | writes it |
| Frontend logic | writes it | reads the diff |
| Bug patch | writes it | reads the diff |
| Review fix over ~20 lines | writes it | reads the diff |
| Review fix, smaller | — | writes it |
| Browser check | pre-check | runs `## Verification` |
| Review | pre-pass, report only | the review |
| git | — | all of it |

Frontend look means the markup and classes: Claude writes them, and leaves the handlers, state and API calls for qwen to fill in. qwen cannot see images (`omp models` says `images: no`).

## Alone

`/dev:offload-to-localLLM <task>`

1. `omp` must be on PATH and the folder must be a git repo. Otherwise say so in one line and stop.
2. Pick a slug from the task, like `snake-game`. The run folder is `dev/<slug>/offload/<run>/`, with `<run>` like `solo`. `dev/` is gitignored; `offload.py start` adds `/dev/` to `.gitignore` when it is missing.
3. Read just enough code to write the brief.
   - The code it needs is under about 300 lines → say so in one line and write it on Claude instead. On the first tests, a 156-line Snake took 8.2 minutes through qwen and 0.7 on Claude, because the brief and the checks cost more than the code.
4. The task changes behaviour → write the tests first, in the repo's own test folder, and see them fail. Name the interface they need, like `next_head(head, direction)`, in the brief. qwen never writes or edits a test.
5. Write `brief.md` in the run folder (below).
6. Run `offload.py start <run-dir>` as a background shell (`run_in_background`) and end your turn. It runs omp as soon as one of the 4 slots is free, with the output in `omp.log` in the run folder, and exits only when the run does. You are woken once, then. Its output has the exit code, qwen's report, and the `omp --resume` line that picks that qwen session back up, which it also saves in `session.txt`. Pass that line on to the user.
   - In the same turn, start `offload.py watch <run-dir>` with the Monitor tool, `timeout_ms` 1800000, description like `qwen solo progress`. It prints a block right away and every 5 minutes: elapsed, ETA, files written, context window, prefill and decode speed, and the server's KV cache and load. The user asked for it, because a run in the background looks like it never moves.
   - Paste each block to the user as it is, with no comment, and end your turn again.
   - The monitor stops after 30 minutes → start it again while the run goes. It ends by itself when the run does, and leaves every block as a row in `progress.md` in the run folder.

## Four runs at a time

One local model serves every run on the machine, so `offload.py` runs at most 4 at once, and `offload.py queue` lists them. On 2026-11-05, 8 at once each went 5 to 6 times slower and all hit the old 60-minute cap (`Deadline exceeded`); 4 fit the server's memory easily.

- Never wait quietly. A 5th run waits in `~/.cache/dev-offload/` for a free slot, and the watch prints `QWEN BUSY: <repo>/<run> has waited …` for it. The session the user talks to tells the user at once, as its own line, before anything else. Thomas, 2026-11-05: "don't ever fucking stop and wait, wasting time. if qwen is unavailable like needs to wait, raise this flag to me".
- Briefs that share no file go at once: start each one as soon as it is written, up to 4. A brief that needs another brief's code waits for that run's result.
- A run has no time limit: it ends when qwen is done. On 2026-11-05 a 60-minute cap cut step 39 off with 5 of its 7 files written. qwen decodes about 41 tokens a second, mostly thinking at `xhigh`, so a big write brief can take more than an hour. `--timeout <duration>` exists for a limit; leave it off.
- The snapshot is taken when the run gets its slot, not when you start it.
- Never start an agent to feed qwen. You can start all 4 runs yourself, and each agent sends its whole conversation again on every turn.
- Wait in the background: `offload.py start <run-dir>` as a background shell plus the 5-minute `watch`, then end your turn. Each turn sends your whole conversation again. The watch wakes you 12 times an hour at most. Never watch `omp.log` or file changes instead: that wakes you on every line, like the helper that reached 1,089 turns on 2026-11-05.
- A run belongs to no shell, so it goes on when your waiting shell is killed. Told it was killed → start `offload.py wait <run-dir>` as a background shell and end your turn again. On 2026-11-05 Claude Code killed an implementer's waiting shell and, before this fix, the qwen run under it died 9 edits in.
7. Check the run (below).
8. Tell the user in four lines: what works now, the verify output, what Claude changed after qwen, and the run folder.

## The brief

A fresh worker reads it with no memory of this conversation. Never write "as discussed".

```
# Brief: <title>
Report: dev/<slug>/offload/<run>/report.md

## Goal
What is true when this is done.

## Files you may change
- `snake.py` (new)

## Interface
The names and signatures the tests call, exactly.

## Steps
One action per line.

## Edge cases
What must happen on the odd paths, like a resized window, an empty input, a full board, two requests at once.

## Verify
The exact commands, run from the repo root. Run each one yourself before you hand it over: a wrong command blocks qwen.

## Do not touch
- the tests named above, and anything else off limits
```

## Checking a run

1. `offload.py check <run-dir>`, straight after the run and before you change anything yourself.
   - It counts as qwen's the files its omp session edited or wrote, plus the brief's `## Files you may change`. Anything else that changed during the run is listed as `OTHER`: another agent's work, or qwen editing through a shell command. Read those too.
   - It checks the branch, HEAD, stash and remote refs are the same in the repo and in every submodule, like `backend/` inside a wrapper repo. It also checks that no protected file was touched, and whether the deep pass is due.
   - `PROTECTED: n touched` → `offload.py restore <run-dir>`, then re-brief.
   - `BRANCH`, `HEAD` or `STASH` changed, or `REMOTES: PUSHED` → stop and tell the user. Never fix it with git yourself.
2. Run every `## Verify` command yourself. Trust that output, not the report. Then run the thing the way a user would: a terminal app in tmux with `remain-on-exit on`, a page in chrome-devtools, an API with curl.
3. `offload.py diff <run-dir>` and read it: only what qwen changed.
4. `DEEP PASS: yes` → read each changed file whole, and the code it calls. Look for what the local model is known to miss:
   - a request that arrives in the middle of a write, and locks
   - cache keys missing a part, like the tenant
   - tenant filters, permissions, money math
   - tests that only reach units, never the real path
5. Everything holds → done. Otherwise, write a test that shows the problem and see it fail, then:
   - the fix is under about 20 lines → make it yourself
   - bigger → re-brief once in a new run folder, like `solo-r2`, with exactly what failed. It fails again → write the code yourself and say so

The deep pass is due when the repo has no `.claude/risky.md`, or when the diff hits it. That file is the whole dev suite's risk list, not only this skill's: design, build and review read it too, the way `## Risk` in `~/.claude/commands/dev/full-dev-cycle.md` says. It lives next to the repo's `.claude/finishing-development.md`, in this shape:

```
## Claude only
- `database/migration/` — runs on prod
## Deep pass
- `shared/util/cache_helper.py` — tenant cache key
## Patterns
- `tenant_id`
```

`## Claude only` paths are protected like tests. `## Patterns` are plain text matched against qwen's added lines. A repo without the file: inside the cycle, the designer drafts it. Used alone, offer once at the end to draft it from the repo's auth, cache, lock, money and migration code, and write it only when the user says yes.

## With another /dev skill

Typed next to another `/dev` skill, that skill runs as usual, with one line in the plan: `Offload: local` under `Ticket:`. `/dev:2-implement` adds it; `/dev:full-dev-cycle` runs 2-implement, so it gets it too. Delete the line to build that plan on Claude again.

A plan with `Offload: local` is built and fixed by the session you talk to, never by a `dev-implementer` agent. An agent that only hands code to qwen adds its own startup, its own reads of the plan and the code, and its own turns, and qwen already runs 4 at once. Thomas, 2026-11-05: "I don't like the idea to use subagent to just handing off a task to local model, it does not make sense". So in the build and in every fix round:

- read `~/.claude/agents/dev-implementer.md` and follow it yourself, with `plan`, plus `fixes` in a fix round
- you build every repo in the plan: the `setup` steps, then each repo's steps, then the `join` steps and `## Verification`
- start the briefs of different repos at once, up to 4, when they share no file
- never stop with `STATUS: partial` and write no `## Report back`: tell the user what now works, the way `/dev:2-implement` step 6 says
- `STATUS: needs-db` or a blocker → ask or tell the user straight away, the way `/dev:2-implement` step 4 says
- start no agent to build or to feed qwen. On 2026-11-05 one backend build started 9 helpers to feed qwen faster. Every first-round run timed out, the helpers wrote most of the code themselves, and they used about 2.36 billion cached-token reads in one night

When you start the first run, or the review pre-pass, start `offload.py watch` with no run folder under Monitor, the same way as in "Alone". With no run folder it follows every run going on this machine, each block titled `<repo>/<run>`, so another session's run shows up too, and it prints `QWEN BUSY` for every run that waits for a slot. Start it again every 30 minutes until your runs are done.

### Each step

Before the first step: add up the code the plan adds, from its `## Code structure` and `## Files`. Under about 300 lines → build it yourself with no qwen, as if there were no `Offload:` line, and tell the user `OFFLOAD: skipped, about <n> lines`. On the first full-cycle test, 390 lines of code took 25.2 minutes with qwen and 14.7 without.

1. Read the step as usual.
2. The step only touches what is Claude's (tests, specs, docs, migrations, the frontend look) → do it yourself.
3. Otherwise write what is Claude's first: the backend test, seen to fail; the frontend markup and classes, with the handlers left empty. Then write `dev/<slug>/offload/step-<N>/brief.md`, with the step's `verify:` under `## Verify`.
   - The plan is the spec, so the brief points at it and never copies it: `## Goal` says "do step N of `plan/<slug>/plan.md`: its `## Detail` block, and the parts of `## Code structure`, `## Flow` and `## Contract` it names". Add only what the plan does not say, like the test names it has to pass. At most 15 lines.
   - Why: on the first full-cycle test the briefs came to 26.8 KB, more than the 15.6 KB of code qwen wrote from them, and Claude spent more tokens than building it alone.
4. `offload.py start <run-dir>` as a background shell, end your turn, and check the run as above when you are woken.
5. Run the step's `verify:` yourself and paste it. Tick the step yourself. qwen never ticks.

### Browser pre-check

Before `## Verification` in a browser: a brief in `dev/<slug>/offload/browser/` asks qwen to click through every screen, using omp's browser tool, and report console errors and failed requests only. Anything red → back to qwen with the error. Then run `## Verification` yourself in chrome-devtools, the same as without offload. A terminal app has no pre-check.

### Review fixes

- A fix over about 20 lines, in code → qwen, in `dev/<slug>/offload/fix-<id>/`.
- Smaller, or in a test, spec or doc → do it yourself.

### Review pre-pass

Round 1 of `/dev:3-review` only. It runs at the same time as Claude's reviewers, never before them, so it adds no wait, and it changes no file. Claude's reviewers are the review; qwen only adds findings they might miss. On the first full-cycle test, a blocking pre-pass that fixed code cost 47.5 minutes over two rounds and fixed nothing, but its one note, a missing socket timeout, was real and Claude's own security lens on that build missed it. A re-review gets no pre-pass.

1. Write `git diff <base>` and the untracked files into `dev/<slug>/offload/review-1/diff.patch`. qwen cannot run git.
2. Brief: review that diff against the plan, with the lenses in `~/.claude/agents/dev-reviewer.md`. List each finding in the report as `qwen-<n> | <file>:<line> | <what breaks, for whom>`. `## Files you may change` is "none".
3. In the same turn you spawn Claude's reviewers, run `offload.py start <run-dir>` as a background shell, so both run together and you are told when qwen is done.
4. Print Claude's findings as soon as they are ready. Never wait for qwen.
5. When qwen's run exits, before the user replies:
   - `offload.py check <run-dir>`. It changed any file → `offload.py restore <run-dir> --all`.
   - Each of its findings that no reviewer reported at the same `file:line` goes into `dev/<slug>/review/qwen.json`, in the reviewer's JSON shape, with `"lens": "qwen"`, an id like `qwen-1`, and `cause` starting "From qwen's pre-pass, not confirmed:".
   - Merge again with `qwen.json` added to the files in `/dev:3-review` step 7, and print just the `qwen-<n>` findings.
   - A false one dies at the fix step, since every fix starts with a test that has to fail first.
6. The user replied before qwen finished → stop the run (`kill -- -<the pid in the run folder's pid file>`) and leave its findings out.

## Hard rules

| Rule | Why |
|---|---|
| qwen never runs git | Claude's safeguard |
| qwen runs with no git credentials | a push has nothing to sign in with |
| Specs, tests, docs are Claude's | bugs there are not caught |
| Never change omp's settings | the git block is `--config`, per run |
| Always `--thinking xhigh` | never downgrade qwen |
| Claude reads every diff | a clean report proves nothing |
| One re-brief, then Claude codes | each round costs Claude tokens |
| No agent just to feed qwen | the session you talk to does it |
| Only Claude ticks the plan | `plan-status.py` counts checked steps |
