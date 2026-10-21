#!/usr/bin/env python3
"""Open a decision page and read the human's picks back, without remembering tab ids.

Usage:
  decision-page.py open <page.html> [--root <worktree>]   open it in Orca's browser (or the default browser)
  decision-page.py answers <page.html>    print the picks as JSON, then close the tab

The Orca tab id is saved next to the page as <page.html>.pageid, so `answers`
works in a later turn or after the session's context was compacted.
Exit codes: 0 ok, 3 no Orca tab (ask the human to paste the JSON), 1 error.
"""
import json
import pathlib
import shutil
import subprocess
import sys


def orca(*args):
    out = subprocess.run(["orca", *args, "--json"], capture_output=True, text=True, timeout=60)
    data = json.loads(out.stdout or "{}")
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or out.stderr.strip() or "orca call failed")
    return data["result"]


def in_orca(root):
    if not shutil.which("orca"):
        return False
    try:
        return any(w.get("path") == str(root) for w in orca("worktree", "list")["worktrees"])
    except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError):
        return False


def git_root(page):
    out = subprocess.run(["git", "-C", str(page.parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return pathlib.Path(out.stdout.strip() or page.parent).resolve()


def cmd_open(page, root=None):
    root = root or git_root(page)
    pageid = page.with_name(page.name + ".pageid")
    if in_orca(root):
        result = orca("tab", "create", "--url", page.as_uri(), "--worktree", f"path:{root}")
        pageid.write_text(result["browserPageId"])
        print(json.dumps({"opened": "orca", "page_id": result["browserPageId"]}))
    else:
        subprocess.run(["open", str(page)], check=False)
        pageid.unlink(missing_ok=True)
        print(json.dumps({"opened": "browser", "page_id": None, "note": "ask the human to paste the JSON"}))


def cmd_answers(page):
    pageid = page.with_name(page.name + ".pageid")
    if not pageid.is_file():
        print(json.dumps({"error": "no Orca tab for this page; ask the human to paste the JSON"}))
        sys.exit(3)
    tab = pageid.read_text().strip()
    try:
        raw = orca("eval", "--page", tab, "--expression", "document.getElementById('out').value")["result"]
    except RuntimeError as e:
        print(json.dumps({"error": f"could not read the tab ({e}); ask the human to paste the JSON"}))
        sys.exit(3)
    answers = json.loads(raw)
    if not answers.get("answers"):
        print(json.dumps({"error": "the page has no answers yet"}))
        sys.exit(1)
    try:
        orca("tab", "close", "--page", tab)
    except RuntimeError:
        pass
    pageid.unlink(missing_ok=True)
    print(json.dumps(answers, ensure_ascii=False))


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("open", "answers"):
        sys.exit(__doc__)
    page = pathlib.Path(args[1]).resolve()
    if not page.is_file():
        sys.exit(f"no such page: {page}")
    if args[0] == "open":
        root = pathlib.Path(args[args.index("--root") + 1]).resolve() if "--root" in args else None
        cmd_open(page, root)
    else:
        cmd_answers(page)


if __name__ == "__main__":
    main()
