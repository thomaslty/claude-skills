#!/usr/bin/env python3
"""Remember a repo's files now, and show later what changed since. Writes nothing in git.

Usage:
  changes.py snapshot <dir> [--root <repo>]
  changes.py list     <dir>
  changes.py diff     <dir>

<dir> holds the snapshot: snapshot.json, and before/ with a copy of every file
that had uncommitted changes. Put it under the repo's gitignored dev/ folder,
like dev/<slug>/review/fix-1/. --root is the repo, and defaults to the git repo
that holds <dir>.

snapshot  remembers every tracked and untracked file, the branch, HEAD, the
          stash and the remote refs
list      every file added, modified or deleted since, one per line
diff      only what changed since, as a unified diff

Used by /dev:3-review, so the re-review reads only what the fixes changed,
and by offload.py, for what qwen changed.
"""
import argparse
import difflib
import fnmatch
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

MAX_COPY = 5 * 1024 * 1024  # bytes; a bigger dirty file is hashed but not copied

# Build output a run leaves behind. Nobody wrote it, so it is never counted.
ARTIFACTS = ["*__pycache__/*", "*.pyc", "*.pytest_cache/*", "*.DS_Store", "*node_modules/*"]


def git(root, *args):
    """git's stdout, or None when git fails."""
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def repo_root(path):
    """The top of the git repo that holds `path`."""
    top = git(path, "rev-parse", "--show-toplevel")
    if not top:
        sys.exit(f"{path} is not inside a git repo")
    return pathlib.Path(top.strip())


def is_artifact(rel):
    """True when the file is build output, like a .pyc."""
    return any(fnmatch.fnmatch(rel, a) for a in ARTIFACTS)


def tracked_and_untracked(root):
    """Every file git tracks or would add, minus gitignored files and build output."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                         capture_output=True).stdout.decode()
    return sorted({p for p in out.split("\0") if p and not is_artifact(p)})


def sha(path):
    """The file's hash, or None when it is gone."""
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except (FileNotFoundError, IsADirectoryError):
        return None


def is_binary(path):
    """True when the file has a NUL byte in its first 8 KB."""
    try:
        return b"\0" in path.read_bytes()[:8192]
    except (FileNotFoundError, IsADirectoryError):
        return False


def head_text(root, rel, rev="HEAD"):
    """The file as commit `rev` has it, or None when that commit does not have it."""
    r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{rel}"], capture_output=True)
    return r.stdout.decode(errors="replace") if r.returncode == 0 else None


def stash_count(root):
    """How many stash entries the repo has."""
    out = git(root, "stash", "list") or ""
    return len([l for l in out.splitlines() if l.strip()])


def remote_refs(root):
    """Each remote-tracking ref and the commit it points at; a push moves one."""
    out = git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes") or ""
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line)


def dirty_files(root):
    """Paths with uncommitted changes, untracked ones included."""
    out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z", "--untracked-files=all"],
                         capture_output=True).stdout.decode()
    dirty, entries, i = set(), out.split("\0"), 0
    while i < len(entries):
        e = entries[i]
        if len(e) > 3:
            dirty.add(e[3:])
            if e[0] in "RC":  # a rename has its old path in the next entry
                i += 1
        i += 1
    return dirty


def snapshot(root, dest, extra=None):
    """Write dest/snapshot.json and dest/before/, and return the snapshot."""
    dest.mkdir(parents=True, exist_ok=True)
    before = dest / "before"
    if before.exists():
        shutil.rmtree(before)
    dirty = dirty_files(root)
    hashes = {}
    for rel in tracked_and_untracked(root):
        p = root / rel
        h = sha(p)
        if h is None:
            continue
        hashes[rel] = h
        if rel in dirty and p.stat().st_size <= MAX_COPY:
            copy = before / rel
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, copy)
    head = git(root, "rev-parse", "HEAD")
    snap = {
        "root": str(root),
        "branch": (git(root, "branch", "--show-current") or "").strip(),
        "head": head.strip() if head else None,
        "stash": stash_count(root),
        "remotes": remote_refs(root),
        "hashes": hashes,
        "time": time.time(),
        **(extra or {}),
    }
    (dest / "snapshot.json").write_text(json.dumps(snap))
    return snap


def load(dest):
    """The snapshot in `dest`, with its repo root."""
    dest = pathlib.Path(dest).resolve()
    f = dest / "snapshot.json"
    if not f.exists():
        sys.exit(f"no snapshot in {dest}: run `changes.py snapshot {dest}` first")
    snap = json.loads(f.read_text())
    return dest, pathlib.Path(snap["root"]), snap


def changes(root, snap):
    """Every (path, added | modified | deleted) since the snapshot."""
    now = {rel: sha(root / rel) for rel in tracked_and_untracked(root)}
    now = {k: v for k, v in now.items() if v}
    old = {k: v for k, v in snap["hashes"].items() if not is_artifact(k)}
    out = []
    for rel in sorted(set(old) | set(now)):
        if old.get(rel) == now.get(rel):
            continue
        kind = "added" if rel not in old else "deleted" if rel not in now else "modified"
        out.append((rel, kind))
    return out


def before_text(root, dest, rel, snap):
    """The file as it was at the snapshot: the copy, else the snapshot's commit, else empty."""
    copy = dest / "before" / rel
    if copy.exists():
        return copy.read_text(errors="replace")
    if rel in snap["hashes"] and snap["head"]:
        # the snapshot's commit, not today's HEAD: an implementer may commit after the snapshot
        t = head_text(root, rel, snap["head"])
        if t is not None:
            return t
    return ""


def added_lines(old, new):
    """Each (line number, text) in `new` that is not in `old`."""
    a, b = old.splitlines(), new.splitlines()
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                yield j + 1, b[j]


def diff_text(root, dest, snap):
    """A unified diff of everything that changed since the snapshot."""
    out = []
    for rel, kind in changes(root, snap):
        if is_binary(root / rel) or is_binary(dest / "before" / rel):
            out.append(f"Binary file {rel} {kind}\n")
            continue
        old = before_text(root, dest, rel, snap) if kind != "added" else ""
        new = (root / rel).read_text(errors="replace") if kind != "deleted" else ""
        out.extend(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        if new and not new.endswith("\n"):
            out.append("\n")
    return "".join(out)


def main(argv=None):
    """Run the snapshot, list or diff command."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("dir")
    s.add_argument("--root")
    sub.add_parser("list").add_argument("dir")
    sub.add_parser("diff").add_argument("dir")
    a = ap.parse_args(argv)
    if a.cmd == "snapshot":
        dest = pathlib.Path(a.dir).resolve()
        start = dest
        while not start.exists():  # dev/<slug>/review/fix-1/ may not exist yet
            start = start.parent
        root = repo_root(pathlib.Path(a.root).resolve() if a.root else start)
        snap = snapshot(root, dest)
        print(f"SNAPSHOT: {len(snap['hashes'])} files in {root}, saved to {dest}")
        return 0
    dest, root, snap = load(a.dir)
    if a.cmd == "list":
        for rel, kind in changes(root, snap):
            print(f"{kind:8} {rel}")
    else:
        sys.stdout.write(diff_text(root, dest, snap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
