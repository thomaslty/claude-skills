# Token burn — root cause TLDR

4,746 session logs in `~/.claude/projects`, every repo and all 3 Orca profiles, 2026-04-02 → 2026-11-04, 168,081 API calls. $ is API list price, so it is what the tokens are worth, not your plan bill.

## TLDR

You don't burn tokens on what you type, you burn them re-reading. Every call sends the whole context again, and the context is big.

- 53% of the last 30 days ($1,783 of $3,344) is cache reads, 64% all time
- the average call re-reads 265k tokens, and calls past 200k are 64% of the spend
- subagents are 65% of the last 30 days, `dev-implementer` alone is 34%
- 24 sessions, the top 5%, are 93% of the last 30 days
- unused skills and plugins were ~1.3k tokens per call, under 1% of spend, removed anyway

## Where the money goes

| Bucket | Last 30 days | All time |
|---|---|---|
| Calls | 37,021 | 168,081 |
| Spend | $3,344 | $29,944 |
| Cache read | 53% | 64% |
| Cache write | 27% | 22% |
| Output + thinking | 20% | 13% |
| Avg context per call | 265k | 245k |

The July peak ($7,262) was mostly price. Fable 5 reads cache at $1/M, Opus 5 and 4.x at $0.50/M, Opus 5.5 at $0.20/M. October had more calls than July (24,646 vs 23,391) and cost a third.

## Root causes, biggest first

| # | Root cause | Last 30 days |
|---|---|---|
| 1 | Context never resets | 64% of $ |
| 2 | dev-implementer runs long | $1,135 |
| 3 | Files read through Bash | 22% of context |
| 4 | Fixed setup per call | 58k–112k tokens |
| 5 | xhigh effort everywhere | $666 output |
| 6 | Unused skills + plugins | ~$10 |

They overlap. #2 is mostly #1 inside a subagent, and #3 and #4 are what fills #1.

### 1. Context never resets

- `modelSettings.claude-opus-5-5.autoCompactWindow` is `"auto"` on `opus[1m]` in `~/.claude/settings.json`, so compaction waits until close to 1M
- only 20 of 484 main sessions compacted in the last 30 days
- like session `95792ccc` (Omega.Next.AIO `feat-validation-engine`, 2026-10-27): 5,439 calls, and Claude Code's own `cost-state` logged 1.86B cache-read tokens and $581 for it
- calls above 300k re-read 1.78B tokens past that line in 30 days, $356
- a smaller window is not the fix: `/autocompact` at 400k on 2026-10-22 made a `dev-implementer` compact 4 times in an hour (session `b416e768`, 2026-10-28), so 1M stays

### 2. dev-implementer runs one huge context

- 77 runs, 11,153 calls, 145 calls per run, 326k context per call, more than the main thread (268k)
- its first call is already 80,019 tokens (`5b7cd6e6` subagent `agent-aa32dfc0a28110371`), then the plan, code and test output pile on until it ends
- `dev-reviewer` is next, $434 over 7,100 calls at 133k
- each subagent writes its own ~66k setup to cache, it can't reuse the parent's cache, which is part of the 27% cache write

### 3. Files read through Bash

- Bash output is 22% of everything re-read in 30 days, and half of it is file reads: `cat` 27%, `sed -n` 25%, `grep` 12% of the Bash share
- like `sed -n 214,306p plan/designer-round-3-feedback/plan.md`, which returned 29,761 chars that stay for the rest of the session
- 4,216 `cat` calls averaged 6,142 chars, the biggest stop at the 30,000-char `bashOutputMaxChars` default

### 4. Fixed setup per call

Before any work, a main-thread call in this repo carries ~58k tokens, and one in Omega.Next.AIO ~112k. That is about 27% of everything re-read.

| Part | Tokens per call |
|---|---|
| Built-in tool schemas | 16.8k |
| Artifact tool schema | 14.9k |
| conventions.md (Omega) | 14.6k–21.7k |
| Skills list | 12.0k |
| MEMORY.md (Omega) | 8.2k |
| CLAUDE.md (Omega) | 6.6k–7.3k |
| Global CLAUDE.md | 4.5k |
| Deferred tools list | 4.2k |
| Agent types list | 3.7k |
| System prompt | 3.3k |
| MCP instructions | 2.0k |
| Omega LINK hook output | 1.3k |

- the skills list has a fixed size: `skillListingBudgetFraction`, 1% of the context window, ~30k chars on `opus[1m]`; past that the descriptions get shorter, so fewer skills does not make it smaller (148 skills and 93 skills both came to ~30k chars)
- the Omega SessionStart block in `5b7cd6e6` is 62,410 chars, but the `LINK` lines from `scripts/link-claude.sh` are only 3,209 of it; the rest is the skills list, deferred tools, agent types and MCP instructions
- subagents get the whole CLAUDE.md stack too: `dev-reviewer`'s first call is 46,357 tokens, and 39k of it is conventions.md + MEMORY.md + the two CLAUDE.md files
- `conventions.md` only grows, since `dev-convention-learner` merges into it after every phase: 39,923 chars in `fix-omega-entity-deployment`, 54,351 in `feat-crypto-with-pe`
- the Omega `MEMORY.md` index is 118 lines at 174 chars each, with deploy status and commit hashes inside the index lines
- `dev-implementer` has all tools, so it also carries the 14.9k Artifact schema and the 12k skills list on every call

### 5. xhigh effort everywhere

- `effortLevel: "xhigh"` in settings and in `modelSettings`, and no agent overrides it, so 88% of the last 30 days ran at xhigh
- output + thinking is $666 (20%), and $426 of that is subagents, like `dev-implementer` $199 and `dev-reviewer` $99

### 6. Unused skills and plugins

- 56 of the 148 skills, 6 agent lines, the Postman SessionStart hook and 5 tool names came from things with no use in 60 days
- the skills list stayed at its ~30k-char budget after the removal, so the saving is the agent lines, the hook and the tool names: ~1.3k tokens per call, ~$10 in 30 days
- it does cost on every call, it is just small next to #1–#4
