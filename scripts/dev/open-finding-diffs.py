#!/usr/bin/env python3
"""Open one diff tab per file a review finding points at, nothing else.

Usage: open-finding-diffs.py docs/reviews/<slug>.findings.json

`orca file open-changed` opens every changed file in the worktree, which buries the
few files that matter. This opens only the files named in each finding's `where`,
once each, in the Orca worktree that holds them. A file Orca cannot diff (a new,
untracked one, or one inside a submodule) opens as a plain file tab instead.
Outside Orca it does nothing. Prints {"opened": [...], "skipped": [...]}.
"""
import json
import pathlib
import shutil
import subprocess
import sys


def orca(*args):
    out = subprocess.run(["orca", *args, "--json"], capture_output=True, text=True, timeout=60)
    return out.returncode == 0 and json.loads(out.stdout or "{}").get("ok", False)


def worktrees():
    out = subprocess.run(["orca", "worktree", "list", "--json"], capture_output=True, text=True, timeout=60)
    try:
        return [w["path"] for w in json.loads(out.stdout)["result"]["worktrees"]]
    except (ValueError, KeyError):
        return []


def main():
    findings = json.loads(pathlib.Path(sys.argv[1]).read_text())
    files = list(dict.fromkeys(f["where"].rsplit(":", 1)[0] for f in findings if f.get("where")))
    if not shutil.which("orca") or not files:
        print(json.dumps({"opened": [], "skipped": files}))
        return
    # The deepest Orca worktree that contains the file owns its tab.
    roots = sorted(worktrees(), key=len, reverse=True)
    opened, skipped = [], []
    for path in files:
        root = next((r for r in roots if path.startswith(r.rstrip("/") + "/")), None)
        if root is None:
            skipped.append(path)
            continue
        if orca("file", "diff", path, "--worktree", f"path:{root}") or orca("file", "open", path, "--worktree", f"path:{root}"):
            opened.append(path)
        else:
            skipped.append(path)
    print(json.dumps({"opened": opened, "skipped": skipped}))


if __name__ == "__main__":
    main()
