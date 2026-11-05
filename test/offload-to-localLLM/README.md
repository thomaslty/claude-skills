# offload-to-localLLM test

Each folder is its own git repo with no commits, so `git status` at the top shows them as untracked.

- `1-solo` — `/dev:offload-to-localLLM` alone on the Snake prompt, qwen writes `snake.py`
- `3-solo` — the same brief and tests as `1-solo`, Claude writes `snake.py`
- `2-full-cycle` — `/dev:full-dev-cycle + /dev:offload-to-localLLM` on Snake plus a per-tenant leaderboard
- `4-full-cycle` — the same ticket and plan as `2-full-cycle` with `Offload: local` taken out, Claude only

## Run it again

- you have to run the tests from inside a folder, like `cd 2-full-cycle && python3 -m unittest discover -s tests`
- qwen's briefs, reports and `omp --resume` lines are in `dev/<slug>/offload/<run>/`
- the review findings are in `dev/<slug>/review/`, round 1 in `round1/`

## What it showed (2026-11-04)

- offloading saved no Claude tokens at this size: the full cycle used about 8% more Claude output tokens and 39% more in total, and took about 1.8x as long
- the briefs Claude wrote were bigger than the code qwen wrote from them (26.8 KB vs 15.6 KB), so the skill now points briefs at the plan instead
- qwen broke no rule: 0 protected files touched and no git command in 6 runs
- qwen's key-speed fix left one more bug (a quick U-turn drops both turns) that Claude's fix did not have
- on the small task, both models missed the same terminal-resize crash, because the brief never asked for it
- maybe it pays off on bigger code-heavy tickets, where the code dwarfs the brief; this test did not reach that size
