#!/usr/bin/env python3
"""Hand one brief to qwen through omp, wait for it, then check what it changed.

Usage:
  offload.py start   <run-dir> [--max-time 60m] [--wait 540]
  offload.py wait    <run-dir> [--wait 540]
  offload.py check   <run-dir>
  offload.py diff    <run-dir>
  offload.py restore <run-dir> [--all]

<run-dir> is dev/<slug>/offload/<run>/ inside a git repo. Claude writes
brief.md there first. qwen writes report.md there.

start    snapshots the repo, runs omp in the background, then waits like
         `wait`. The output goes to omp.log in the run folder.
wait     waits up to --wait seconds. Prints STATUS: running, or the exit code,
         qwen's report, and the omp session to resume. Run it again while it
         says running.
check    the free checks: same branch, HEAD, stash and remote refs, no
         protected file touched, and whether Claude's deep pass is due
         (.claude/risky.md).
diff     only what qwen changed, as a unified diff against the snapshot.
restore  puts every protected file qwen touched back the way it was; with
         --all, every file it touched, for a report-only run.

Never runs a git command that writes. omp's own settings are never changed:
the git block is passed with `omp --config offload-omp.yml` for each run, and
omp runs with no git or GitHub credentials in its environment.
"""
import argparse
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import changes as ch  # noqa: E402  the shared snapshot and diff

RULES = HERE / "offload-worker-rules.md"
OVERLAY = HERE / "offload-omp.yml"
RISKY_FILE = ".claude/risky.md"

# Specs, tests and instructions are Claude's. qwen reads them and never writes them.
PROTECTED = [
    "test/*", "tests/*", "*/test/*", "*/tests/*",
    "test_*.py", "*/test_*.py", "*_test.py", "conftest.py", "*/conftest.py",
    "*.test.*", "*.spec.*", "e2e/*", "*/e2e/*",
    "openspec/*", "*/openspec/*", "plan/*", "dev/*",
    "README.md", "*/README.md", "docs/*", "*/docs/*",
    "DESIGN.md", "*/DESIGN.md", "CONTEXT.md", "*/CONTEXT.md",
    "CLAUDE.md", "*/CLAUDE.md", "AGENTS.md", "*/AGENTS.md",
    ".claude/*", "*/.claude/*",
]

# What omp runs without, so a push from inside a run has nothing to sign in with.
# Apple's git keeps its keychain helper in the system config, hence NOSYSTEM.
NO_CREDENTIALS = ["env", "-u", "SSH_AUTH_SOCK", "-u", "SSH_ASKPASS", "-u", "GIT_ASKPASS",
                  "-u", "GH_TOKEN", "-u", "GITHUB_TOKEN",
                  "GIT_CONFIG_GLOBAL=/dev/null", "GIT_CONFIG_NOSYSTEM=1", "GIT_TERMINAL_PROMPT=0"]


def risky(root):
    """Sections of .claude/risky.md: Claude only, Deep pass, Patterns."""
    f = root / RISKY_FILE
    if not f.exists():
        return None
    sections, cur = {}, None
    for line in f.read_text().splitlines():
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            sections[cur] = []
        elif cur and line.lstrip().startswith("- "):
            m = re.search(r"`([^`]+)`", line)
            if m:
                sections[cur].append(m.group(1))
    return {"claude only": sections.get("claude only", []),
            "deep pass": sections.get("deep pass", []),
            "patterns": sections.get("patterns", [])}


def matches(rel, globs):
    """True when `rel` is one of the paths or folders in `globs`."""
    for g in globs:
        g = g.rstrip("/")
        if ch.fnmatch.fnmatch(rel, g) or ch.fnmatch.fnmatch(rel, g + "/*") or rel == g:
            return True
    return False


def omp_session(root, since):
    """The omp session this run wrote: started in `root` after `since`."""
    best = None
    for f in pathlib.Path.home().glob(".omp/agent/sessions/*/*.jsonl"):
        if f.stat().st_mtime < since:
            continue
        try:
            with open(f) as fh:
                for line in fh:
                    d = json.loads(line)
                    if d.get("type") == "session":
                        break
                else:
                    continue
        except (ValueError, OSError):
            continue
        if d.get("cwd") == str(root) and ts(d.get("timestamp")) >= since - 5:
            if best is None or f.stat().st_mtime > best.stat().st_mtime:
                best = f
    return best


def ts(s):
    """An ISO time as seconds, or 0 when it does not parse."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return 0


def cmd_start(a):
    """Snapshot the repo, start omp in the background, then wait."""
    run = pathlib.Path(a.run).resolve()
    if not (run / "brief.md").exists():
        sys.exit(f"write {run}/brief.md first")
    if not shutil.which("omp"):
        sys.exit("omp is not on PATH")
    root = ch.repo_root(run)
    ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(run / "brief.md")]).returncode == 0
    if not ignored:
        gi = root / ".gitignore"
        text = gi.read_text() if gi.exists() else ""
        gi.write_text(text + ("" if text.endswith("\n") or not text else "\n") + "/dev/\n")
        print("added /dev/ to .gitignore")
    for stale in ("exit_code", "report.md", "omp.log", "session.txt"):
        (run / stale).unlink(missing_ok=True)
    ch.snapshot(root, run, {"brief": ch.sha(run / "brief.md")})
    rel = run.relative_to(root)
    message = f"Your brief is attached. Do it, then write your report to {rel}/report.md."
    omp = [*NO_CREDENTIALS, "omp", "-p", "--thinking", "xhigh", "--no-title", "--max-time", a.max_time,
           "--config", str(OVERLAY), "--append-system-prompt", str(RULES),
           message, f"@{run / 'brief.md'}"]
    script = run / "cmd.sh"
    script.write_text(
        "#!/bin/bash\n"
        f"cd {shlex.quote(str(root))} || exit 97\n"
        f"{shlex.join(omp)} 2>&1 | tee {shlex.quote(str(run / 'omp.log'))}\n"
        f"echo \"${{PIPESTATUS[0]}}\" > {shlex.quote(str(run / 'exit_code'))}\n"
    )
    script.chmod(0o755)
    log = open(run / "launch.log", "w")
    p = subprocess.Popen(["bash", str(script)], stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    (run / "pid").write_text(str(p.pid))
    print(f"RUNNING: background pid {p.pid}, output in {rel}/omp.log")
    cmd_wait(a)


def cmd_wait(a):
    """Wait up to --wait seconds, then print the exit code, the session and the report."""
    run = pathlib.Path(a.run).resolve()
    done = run / "exit_code"
    end = time.time() + a.wait
    while time.time() < end and not done.exists():
        time.sleep(5)
    if not done.exists():
        log = run / "omp.log"
        lines = log.read_text(errors="replace").count("\n") if log.exists() else 0
        print(f"STATUS: running ({lines} log lines). Run `offload.py wait {run}` again.")
        return
    code = done.read_text().strip()
    print(f"STATUS: exited {code}")
    snap_file = run / "snapshot.json"
    if snap_file.exists():
        snap = json.loads(snap_file.read_text())
        session = omp_session(pathlib.Path(snap["root"]), snap["time"])
        if session:
            (run / "session.txt").write_text(str(session) + "\n")
            print(f"SESSION: omp --resume {shlex.quote(str(session))}")
    report = run / "report.md"
    if report.exists():
        print("--- report.md")
        print("\n".join(report.read_text(errors="replace").splitlines()[:40]))
    else:
        print("--- no report.md. Last lines of omp.log:")
        log = run / "omp.log"
        if log.exists():
            print("\n".join(log.read_text(errors="replace").splitlines()[-15:]))


def cmd_check(a):
    """Print the free checks, then PASS or FAIL."""
    run, root, snap = ch.load(a.run)
    bad = False
    branch = (ch.git(root, "branch", "--show-current") or "").strip()
    head = (ch.git(root, "rev-parse", "HEAD") or "").strip() or None
    stash = ch.stash_count(root)
    print(f"BRANCH: {'ok' if branch == snap['branch'] else 'CHANGED'} ({snap['branch']} -> {branch})")
    print(f"HEAD: {'ok' if head == snap['head'] else 'CHANGED'}")
    print(f"STASH: {'ok' if stash == snap['stash'] else 'CHANGED'}")
    bad |= branch != snap["branch"] or head != snap["head"] or stash != snap["stash"]
    if "remotes" in snap:
        now = ch.remote_refs(root)
        moved = sorted(r for r in set(now) | set(snap["remotes"]) if now.get(r) != snap["remotes"].get(r))
        print(f"REMOTES: {'ok' if not moved else 'PUSHED ' + ', '.join(moved)}")
        bad |= bool(moved)
    else:
        print("REMOTES: not recorded in this snapshot")
    if ch.sha(run / "brief.md") != snap.get("brief"):
        print("BRIEF: CHANGED by the run")
        bad = True
    lists = risky(root)
    claude_only = lists["claude only"] if lists else []
    changed = ch.changes(root, snap)
    print(f"CHANGED: {len(changed)} file(s)")
    hits, protected = [], []
    for rel, kind in changed:
        prot = matches(rel, PROTECTED) or matches(rel, claude_only)
        print(f"  {kind:8} {rel}{'   <- PROTECTED' if prot else ''}")
        if prot:
            protected.append(rel)
            continue
        if lists is None:
            continue
        if matches(rel, lists["deep pass"]):
            hits.append(f"{rel}: risky path")
        if kind != "deleted" and lists["patterns"] and not ch.is_binary(root / rel):
            new = (root / rel).read_text(errors="replace")
            for n, line in ch.added_lines(ch.before_text(root, run, rel, snap), new):
                for pat in lists["patterns"]:
                    if pat in line:
                        hits.append(f"{rel}:{n}: `{pat}`")
    if protected:
        bad = True
        print(f"PROTECTED: {len(protected)} touched. Undo them with `offload.py restore {run}`.")
    else:
        print("PROTECTED: ok")
    if lists is None:
        print(f"DEEP PASS: yes, this repo has no {RISKY_FILE}")
    elif hits:
        print(f"DEEP PASS: yes, {len(hits)} hit(s)")
        for h in hits[:30]:
            print(f"  {h}")
    else:
        print("DEEP PASS: no")
    report = run / "report.md"
    status = "missing"
    if report.exists():
        m = re.search(r"STATUS:\s*(\w+)", report.read_text(errors="replace"))
        status = m.group(1) if m else "unreadable"
    print(f"REPORT: {status}")
    print(f"RESULT: {'FAIL' if bad or status != 'done' else 'PASS'}")


def cmd_diff(a):
    """Print only what qwen changed."""
    run, root, snap = ch.load(a.run)
    sys.stdout.write(ch.diff_text(root, run, snap))


def cmd_restore(a):
    """Put every protected file qwen touched back, or with --all every file it touched."""
    run, root, snap = ch.load(a.run)
    lists = risky(root)
    claude_only = lists["claude only"] if lists else []
    n = 0
    for rel, kind in ch.changes(root, snap):
        if not a.all and not (matches(rel, PROTECTED) or matches(rel, claude_only)):
            continue
        p = root / rel
        copy = run / "before" / rel
        if kind == "added":
            p.unlink(missing_ok=True)
            print(f"removed  {rel}")
        elif copy.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copy, p)
            print(f"restored {rel}")
        else:
            t = ch.head_text(root, rel, snap["head"]) if snap["head"] else None
            if t is None:
                print(f"CANNOT restore {rel}: no copy")
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(t)
            print(f"restored {rel}")
        n += 1
    print(f"{n} file(s) put back")


def main():
    """Run one of the commands."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("run")
    s.add_argument("--max-time", default="60m")
    s.add_argument("--wait", type=int, default=540)
    w = sub.add_parser("wait")
    w.add_argument("run")
    w.add_argument("--wait", type=int, default=540)
    for name in ("check", "diff"):
        sub.add_parser(name).add_argument("run")
    r = sub.add_parser("restore")
    r.add_argument("run")
    r.add_argument("--all", action="store_true", help="every changed file, for a report-only run")
    a = ap.parse_args()
    {"start": cmd_start, "wait": cmd_wait, "check": cmd_check,
     "diff": cmd_diff, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    main()
