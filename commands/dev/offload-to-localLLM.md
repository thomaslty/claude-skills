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
6. `offload.py start <run-dir>`. It runs omp in the background, with its output in `omp.log` in the run folder. While it prints `STATUS: running`, run `offload.py wait <run-dir>`. Once it exits, `wait` prints the `omp --resume` line that picks that qwen session back up, and saves it in `session.txt`. Pass that line on to the user.
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

1. `offload.py check <run-dir>`, straight after the run and before you change anything yourself: it counts every change since the snapshot as qwen's. It checks the branch, HEAD, stash and remote refs are the same, that no protected file was touched, and whether the deep pass is due.
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

Typed next to another `/dev` skill, this skill runs nothing itself. That skill runs as usual, with one line in the plan: `Offload: local` under `Ticket:`. `/dev:2-implement` adds it; `/dev:full-dev-cycle` runs 2-implement, so it gets it too. Every agent that reads the plan then works the way the sections below say. Delete the line to build that plan on Claude again.

### Each step, inside dev-implementer

Before the first step: add up the code the plan adds for your repo, from its `## Code structure` and `## Files`. Under about 300 lines → build it on Claude as if there were no `Offload:` line, and say so in your report: `OFFLOAD: skipped, about <n> lines`. On the first full-cycle test, 390 lines of code took 25.2 minutes with qwen and 14.7 without.

1. Read the step as usual.
2. The step only touches what is Claude's (tests, specs, docs, migrations, the frontend look) → do it yourself.
3. Otherwise write what is Claude's first: the backend test, seen to fail; the frontend markup and classes, with the handlers left empty. Then write `dev/<slug>/offload/step-<N>/brief.md`, with the step's `verify:` under `## Verify`.
   - The plan is the spec, so the brief points at it and never copies it: `## Goal` says "do step N of `plan/<slug>/plan.md`: its `## Detail` block, and the parts of `## Code structure`, `## Flow` and `## Contract` it names". Add only what the plan does not say, like the test names it has to pass. At most 15 lines.
   - Why: on the first full-cycle test the briefs came to 26.8 KB, more than the 15.6 KB of code qwen wrote from them, and Claude spent more tokens than building it alone.
4. `offload.py start`, then `wait` until it exits, then check the run as above.
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
3. In the same turn you spawn Claude's reviewers, run `offload.py start <run-dir> --max-time 10m --wait 0`, so both run together. Then start `offload.py wait <run-dir> --wait 660` as a background shell job, so you are told when qwen is done.
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
| Only Claude ticks the plan | `plan-status.py` counts checked steps |
