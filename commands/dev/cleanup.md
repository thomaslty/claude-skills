---
name: cleanup
description: "Stop what this Claude Code session started and left running: background bash scripts, servers like FastAPI/uvicorn or vite, open ports, docker containers, compose projects, and colima when this session started it. Lists first, stops only what you pick. Never touches what another session, your own terminal, or an MCP server started. Triggers on /dev:cleanup, 'clean up the session', 'kill what you started', 'stop the servers you started', 'free the ports'."
argument-hint: "[--dry-run]"
---

# Cleanup

Stops what this session started and left running. Everything goes through `~/.claude/scripts/dev/session-cleanup.py`, it links each item to this Claude process or to a command in this session's transcript.

## 1. Find

```bash
python3 ~/.claude/scripts/dev/session-cleanup.py
```

- It prints JSON with `items`, each has `id`, `what`, `ports`, `started`, `why`, `sure`
- `error` in the JSON → show it in one line and stop
- `items` empty → say "Nothing from this session is still running." and stop

## 2. Show

One table, one row per item, sure ones first:

| # | What | Port | Started | Why | Sure |
|---|---|---|---|---|---|

- `what` and `why` come straight from the JSON, keep the cells short
- a `sure: false` row gets one plain sentence under the table saying why it might not be yours, like "port 3000 is open and a call curled it, but your own terminal may have started it"
- `$ARGUMENTS` is `--dry-run` → stop here

## 3. Ask

One AskUserQuestion:

- "Stop the sure ones (Recommended)", only when there are sure ones
- "Stop all N", only when there are `sure: false` ones
- "Cancel"

The user may type IDs in Other, pass those.

## 4. Stop

```bash
python3 ~/.claude/scripts/dev/session-cleanup.py stop --sure   # or --all, or the IDs
```

Show `results` as a table, # / What / Result. Then one line only if `still_running` or `ports_still_open` is not empty.

## Rules

- Stop only through the script. Never `kill`, `pkill`, `docker rm` or `docker compose down` something the script did not list.
- Compose goes `down` without `-v`, named volumes keep their data. Images and volumes are never removed.
- colima is only offered when this session started it and no other container runs in it.
- Never start colima just to look; when docker is not running there is nothing to clean there.
