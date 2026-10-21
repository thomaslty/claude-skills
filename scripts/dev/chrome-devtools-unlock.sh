#!/bin/bash
# Unlock the chrome-devtools MCP browser when it fails with
# "The browser is already running for ~/.cache/chrome-devtools-mcp/chrome-profile".
#
# Usage: ~/.claude/scripts/dev/chrome-devtools-unlock.sh [--kill]
#   no flag  turns on --isolated for new sessions and says who holds the profile
#   --kill   also kills the holding Chrome, only when it is an orphan or this session's own
set -u
PROFILE="$HOME/.cache/chrome-devtools-mcp/chrome-profile"

# 1. Every new session gets its own throwaway profile. Plugin updates replace
#    the plugin folder, so this is checked on every run.
python3 - <<'EOF'
import json, os
reg = json.load(open(os.path.expanduser("~/.claude/plugins/installed_plugins.json")))
for inst in reg["plugins"].get("chrome-devtools-mcp@claude-plugins-official", []):
    # Claude Code reads .claude-plugin/plugin.json; mcp.json in the same folder is for other agents
    path = os.path.join(inst["installPath"], ".claude-plugin", "plugin.json")
    data = json.load(open(path))
    args = data["mcpServers"]["chrome-devtools"]["args"]
    if "--isolated" in args:
        print(f"isolated: already on in {path}")
    else:
        args.append("--isolated")
        json.dump(data, open(path, "w"), indent=2)
        print(f"isolated: added to {path} (takes effect in new sessions)")
EOF

# The claude process above a pid, or nothing when it has none (orphan).
claude_above() {
  local p=$1
  while [ "${p:-1}" -gt 1 ]; do
    p=$(ps -o ppid= -p "$p" | tr -d ' ')
    case "$(ps -o command= -p "${p:-1}" 2>/dev/null)" in claude*) echo "$p"; return;; esac
  done
}

# 2. Who holds the shared profile. The main Chrome process has no --type= flag.
CHROME=$(ps -axo pid=,command= | grep "Google Chrome --" | grep -- "--user-data-dir=$PROFILE" | grep -v -- "--type=" | awk '{print $1}' | head -1)
if [ -z "$CHROME" ]; then
  echo "holder: none — the profile is free, retry the chrome-devtools call"
  exit 0
fi

OWNER=$(claude_above "$CHROME")
ME=$(claude_above $$)

if [ -z "$OWNER" ]; then
  echo "holder: orphan Chrome pid $CHROME (its claude session is gone)"
elif [ "$OWNER" = "$ME" ]; then
  echo "holder: this session's own Chrome pid $CHROME"
else
  CWD=$(lsof -a -p "$OWNER" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
  echo "holder: another live session — claude pid $OWNER in $CWD, Chrome pid $CHROME"
  echo "not killing it. Ask the user: close that session's browser, or restart this session"
  exit 2
fi

if [ "${1:-}" = "--kill" ]; then
  kill "$CHROME" && echo "killed Chrome pid $CHROME — retry the chrome-devtools call"
fi
