# Token burn — improvement plan

The work left is in `docs/plan/token-burn-instructions-reorg.md`, start there.

## Done 2026-11-04

- removed 23 plugins and 13 skills with no use in 60 days, like `postman`, `figma`, the 10 `*-lsp` plugins (no `LSP` call in any log) and the 11 taste-skill links in `~/.claude/skills`
- moved the 11 taste-skill sources out of `~/.agents/skills` too, and dropped their entries from `~/.agents/.skill-lock.json`
- kept the 7 plugins you use: chrome-devtools-mcp, microsoft-docs, context7, frontend-design, eli5, i-have-adhd, security-guidance
- edited `enabledPlugins` in `~/.claude/settings.json` and in the 3 Orca copies, `~/Library/Application Support/orca/claude-profiles/*/home/settings.json`
- everything is in `~/.claude-token-burn-backup-2026-11-04/`; its `restore.sh` copies back whole settings files, so it also undoes any settings change you made after 2026-11-04
- saves ~1.3k tokens per call, ~$10 per 30 days, the skills list stays at its ~30k-char budget
- not touched: your own suite in this repo with no use in 60 days, the Orca skills, the claude.ai `anthropic-skills:*`, the 14 claude.ai connectors that are not signed in

## Ruled out

| Lever | Why not |
|---|---|
| Compact at 300k–400k | implementer compacts nonstop |
| Smaller Bash output | cut output, wrong answers |
| Silence the LINK hook | only ~1.3k tokens |

- 400k was tried on 2026-10-22 (`/autocompact` in `thlau-1-revive-importing-ui`); on 2026-10-28 a `dev-implementer` in `feat-tokenization` compacted at ~367k four times in an hour and was stopped, so the window stays `auto` (1M)

## Next, biggest saving first

| # | Change | Est. per 30 days |
|---|---|---|
| 1 | Omega instruction reorg | ~$150 |
| 2 | Lower effort per agent | part of $426 |
| 3 | Smaller skills list budget | ~$50 |
| 4 | No Artifact in dev-implementer | ~$34 |

Baseline is $3,344 for the last 30 days.

### 1. Omega instruction reorg

- in progress, `docs/plan/token-burn-instructions-reorg.md`
- every Omega call drops from 85k–103k chars of instruction files to ~32k, a frontend-only subagent never loads the backend ones
- 29,418 Omega calls in 30 days, ~0.6–0.8B tokens

### 2. Lower effort per agent

- in `docs/plan/dev-suite-speedup.md`, its `## Effort` table
- subagent output + thinking was $426 in 30 days, `dev-implementer` $199 and `dev-reviewer` $99 of it

### 3. Smaller skills list budget

- set `"skillListingBudgetFraction": 0.004` in `~/.claude/settings.json` and the 3 Orca copies, default is 0.01 (~30k chars on `opus[1m]`)
- the list drops from ~12k to ~5k tokens on every call in every repo
- skills Claude picks on its own get shorter descriptions and may fire less, the ones you run as `/dev:…` or `/show-plan` don't care

### 4. No Artifact in dev-implementer

- in `docs/plan/token-burn-instructions-reorg.md`, step 6
- the 14.9k-token Artifact schema on each of its 11,418 calls, used 3 times; the designer already writes the design to `dev/<slug>/canvas/project/`

## Check it worked

- re-run the scan a week after the changes, see `1-observation-plan.md`
