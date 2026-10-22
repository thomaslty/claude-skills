#!/usr/bin/env python3
"""Work out where a dev: ticket comes from, so no agent has to parse links by hand.

Usage:
  ticket-source.py [--root <repo>] <the command's $ARGUMENTS>
  ticket-source.py --slugify "<title>"

Prints one JSON object. `kind` is one of:
  file    a plan/<slug>/ticket.md or idea.md  -> path, slug
  jira    a Jira URL or key, like THLAU-1     -> key, url, slug
  notion  a Notion link                       -> page_id, url (slug: --slugify the fetched title)
  text    plain requirement text              -> text, slug
  ask     nothing to go on                    -> reason
`via` says how it was found: argument, tickets-dir, or orca-link.
`note` holds any text typed next to a link.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

HEX32 = re.compile(r"[0-9a-f]{32}")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
URL = re.compile(r"https?://\S+")


def slugify(text, words=6):
    parts = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(parts[:words]) or "ticket"


def notion_id(value):
    """32-hex page id from a raw id, a dashed uuid, or the tail of a URL path segment."""
    value = value.lower()
    m = UUID.search(value)
    if m:
        return m.group(0).replace("-", "")
    found = HEX32.findall(value)
    return found[-1] if found else None


def from_url(url):
    u = urlparse(url)
    host = u.netloc.lower()
    query = parse_qs(u.query)

    if host.endswith("notion.so") or host.endswith("notion.com") or host.endswith("notion.site"):
        # A database-view link carries the open ticket in p=; the path id is the database.
        page = notion_id(query["p"][0]) if "p" in query else notion_id(u.path)
        if not page:
            return {"kind": "ask", "reason": f"no Notion page id in {url}"}
        return {"kind": "notion", "page_id": page, "url": f"https://app.notion.com/p/{page}"}

    if "atlassian.net" in host or "/browse/" in u.path:
        key = None
        if "selectedIssue" in query:
            key = query["selectedIssue"][0]
        else:
            m = re.search(r"/browse/([A-Z][A-Z0-9]+-\d+)", u.path)
            key = m.group(1) if m else None
        if not key:
            return {"kind": "ask", "reason": f"no Jira key in {url}"}
        return {"kind": "jira", "key": key, "url": f"{u.scheme}://{u.netloc}/browse/{key}", "slug": key}

    return None


def orca_link(root):
    """Jira ticket Orca linked to this worktree when you sent the ticket to it."""
    if not shutil.which("orca"):
        return None
    try:
        out = subprocess.run(["orca", "worktree", "list", "--json"], capture_output=True, text=True, timeout=20)
        worktrees = json.loads(out.stdout)["result"]["worktrees"]
    except (subprocess.SubprocessError, ValueError, KeyError):
        return None
    for w in worktrees:
        if w.get("path") == str(root):
            item = w.get("linkedWorkItem") or {}
            if item.get("provider") == "jira" and item.get("jiraIdentifier"):
                key = item["jiraIdentifier"]
                return {"kind": "jira", "key": key, "url": item.get("url"), "slug": key}
    return None


def resolve(arg, root):
    arg = arg.strip()

    if not arg:
        tickets = sorted(root.glob("plan/*/ticket.md"))
        if len(tickets) == 1:
            return {"kind": "file", "path": str(tickets[0].relative_to(root)), "slug": tickets[0].parent.name, "via": "tickets-dir"}
        linked = orca_link(root)
        if linked:
            return {**linked, "via": "orca-link"}
        reason = f"{len(tickets)} tickets in plan/" if tickets else "no argument, no plan/*/ticket.md, no Orca link"
        return {"kind": "ask", "reason": reason}

    path = root / arg
    if arg.endswith(".md") and path.is_file():
        # plan/<slug>/ticket.md and idea.md name their slug by their folder
        slug = path.parent.name if path.name in ("ticket.md", "idea.md") else path.stem
        return {"kind": "file", "path": arg, "slug": slug, "via": "argument"}

    if JIRA_KEY.match(arg):
        return {"kind": "jira", "key": arg, "url": None, "slug": arg, "via": "argument"}

    m = URL.search(arg)
    if m:
        found = from_url(m.group(0).rstrip(").,>"))
        if found:
            note = " ".join((arg[: m.start()] + arg[m.end():]).split())
            return {**found, "via": "argument", **({"note": note} if note else {})}

    return {"kind": "text", "text": arg, "slug": slugify(arg), "via": "argument"}


def main():
    args = sys.argv[1:]
    if args[:1] == ["--slugify"]:
        print(slugify(" ".join(args[1:])))
        return
    root = None
    if args[:1] == ["--root"]:
        root, args = pathlib.Path(args[1]), args[2:]
    if root is None:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        root = pathlib.Path(top.stdout.strip() or ".")
    print(json.dumps(resolve(" ".join(args), root.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
