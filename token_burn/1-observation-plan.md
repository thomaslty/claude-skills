# Token burn — observation plan

How the numbers in `2-root-cause-tldr.md` were measured, and how you re-measure after `3-improvement-plan.md`.

## Sources

| Source | Gives |
|---|---|
| `~/.claude/projects/*/*.jsonl` | main-thread sessions |
| `*/<session>/subagents/*.jsonl` | one file per subagent |
| `agent-*.meta.json` | subagent type |
| `message.usage` | tokens per API call |
| `cost-state` rows | Claude Code's own $ |
| `api-request` + blobs | exact request body |

- all 3 Orca profiles link `projects` to `~/.claude/projects`, so this covers every session on this Mac, every repo
- request bodies only exist from October 2026 on, older logs only have usage

## Method

1. take each assistant row's `usage` once per `message.id`: input, cache write 5m, cache write 1h, cache read, output
2. price at list price, the fit against `cost-state` gives Opus 5.5 $4 / $20 / $0.20 / $5 / $8 per M, same as the list
3. split by month, model, repo, main vs subagent type, effort and context size per call
4. for what fills the context: every tool result, prompt, reminder and Claude's own output counts its size × the calls after it, until a compaction
5. chars to tokens at 2.5–3, measured on 824 requests that rebuild completely from blobs
6. for the fixed setup: cut the first request of a fresh session into its sections
7. for use: count `Skill` calls, slash commands, `Agent` `subagent_type` and `mcp__*` tool names, with the last date seen

## Limits

- content shares are ±20%, since most request blobs are missing and they come from the transcript instead
- one base64 PDF had to be left out, `lakehouse_sync.pdf` at 16.3M chars, a PDF is billed per page
- $ is API list price, your plan may count it differently
- the scan counts 18% fewer cache-read tokens than `cost-state` for the biggest session (`95792ccc`), so totals are a floor
- the first request's SessionStart block holds several sections in one text block, split it by its headings before you name a cost after one of them (the first version of these docs called the whole 62k block "LINK hook output")

## Re-run

```bash
# read every log, ~10 seconds
python3 -I token_burn/scripts/scan.py /tmp/scan.json
# same tables, only calls from that date on
python3 -I token_burn/scripts/analyze.py /tmp/scan.json 2026-11-04
```

## Watch

| Metric | Last 30 days | Target |
|---|---|---|
| Avg context per call | 265k | lower |
| $ from calls over 200k | 64% | lower |
| dev-implementer avg context | 326k | lower |
| Instruction files, Omega call | 85k–103k chars | ~32k chars |
| Spend at xhigh | 88% | under 60% |
| Main sessions compacted | 20 of 484 | more is fine |
