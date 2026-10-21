#!/usr/bin/env python3
"""Move this worktree's Orca card to a dev: phase. Changes nothing outside Orca.

Usage: orca-card.py <phase> [--root <worktree>] [--dry-run]

Phases and what they set (column id, card comment, unread dot):
"""
import json
import pathlib
import shutil
import subprocess
import sys

# Column ids are Orca's defaults. If you add Design / Implement columns in
# Orca's settings, change the ids here and nowhere else.
PHASES = {
    "draft":             ("todo",        "draft",              False),
    "design":            ("in-progress", "design",             False),
    "waiting-decisions": (None,          "waiting: decisions", True),
    "implement":         ("in-progress", "implement",          False),
    "blocked":           (None,          "blocked",            True),
    "review":            ("in-review",   "review",             False),
    "waiting-review":    (None,          "waiting: review",    True),
    "fixing":            ("in-progress", "fixing",             False),
    "ready":             ("in-review",   "ready to land",      True),
    "done":              ("completed",   "done",               False),
}
__doc__ += "\n".join(f"  {k:<18} {v[0] or '(keep column)':<14} {v[1]!r}{'  + unread' if v[2] else ''}" for k, v in PHASES.items())


def main():
    args = sys.argv[1:]
    if not args or args[0] not in PHASES:
        sys.exit(__doc__)
    phase = args[0]
    if "--root" in args:
        root = pathlib.Path(args[args.index("--root") + 1]).resolve()
    else:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        root = pathlib.Path(top.stdout.strip() or ".").resolve()

    if not shutil.which("orca"):
        print(json.dumps({"skipped": "orca is not on PATH"}))
        return
    listed = subprocess.run(["orca", "worktree", "list", "--json"], capture_output=True, text=True, timeout=30)
    try:
        worktrees = json.loads(listed.stdout)["result"]["worktrees"]
    except (ValueError, KeyError):
        print(json.dumps({"skipped": "could not list Orca worktrees"}))
        return
    if not any(w.get("path") == str(root) for w in worktrees):
        print(json.dumps({"skipped": f"{root} is not an Orca worktree"}))
        return

    status, comment, unread = PHASES[phase]
    cmd = ["orca", "worktree", "set", "--worktree", f"path:{root}", "--comment", comment, "--json"]
    if status:
        cmd += ["--workspace-status", status]
    if unread:
        cmd.append("--unread")
    if "--dry-run" in args:
        print(json.dumps({"phase": phase, "would_run": cmd}))
        return
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    ok = '"ok": true' in out.stdout or '"ok":true' in out.stdout
    print(json.dumps({"phase": phase, "column": status, "comment": comment, "unread": unread, "ok": ok}))
    if not ok:
        print(out.stdout or out.stderr, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
