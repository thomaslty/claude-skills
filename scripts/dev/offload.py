#!/usr/bin/env python3
"""Hand one brief to qwen through omp, wait for it, then check what it changed.

Usage:
  offload.py start   <run-dir> [--max-time 60m] [--wait 540 | --until-done]
  offload.py wait    <run-dir> [--wait 540 | --until-done]

An agent runs `start <run-dir> --until-done` as a background shell and ends its
turn: it is woken once, when the run ends, and pays nothing while qwen works.
  offload.py check   <run-dir>
  offload.py diff    <run-dir>
  offload.py restore <run-dir> [--all]
  offload.py queue

<run-dir> is dev/<slug>/offload/<run>/ inside a git repo. Claude writes
brief.md there first. qwen writes report.md there.

start    queues the run and returns, then waits like `wait`. One qwen run
         goes at a time on this machine: the others wait in a queue in
         ~/.cache/dev-offload/. The snapshot is taken and --max-time starts
         only when the run's turn comes. The output goes to omp.log in the
         run folder.
wait     waits up to --wait seconds. Prints STATUS: queued (with how many
         runs are ahead), running, or the exit code, qwen's report, and the
         omp session to resume. Run it again while it is not done.
queue    every run queued or running on this machine.
check    the free checks: same branch, HEAD, stash and remote refs, no
         protected file touched, and whether Claude's deep pass is due
         (.claude/risky.md). Counts as qwen's only the files its omp session
         edited or wrote, plus the brief's `## Files you may change`; other
         files that changed during the run are listed as OTHER, not counted.
diff     only what qwen changed, as a unified diff against the snapshot.
restore  puts every protected file qwen touched back the way it was; with
         --all, every file it touched, for a report-only run.

Never runs a git command that writes. omp's own settings are never changed:
the git block is passed with `omp --config offload-omp.yml` for each run, and
omp runs with no git or GitHub credentials in its environment.
"""
import argparse
import fcntl
import json
import os
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
# One local model serves every run. Runs started together slow each other down
# until omp gives up ("Deadline exceeded": 8 of 8 on 2026-11-05), so they queue here.
QUEUE = pathlib.Path.home() / ".cache" / "dev-offload"

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
    """Queue the run in the background, then wait."""
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
    for stale in ("exit_code", "report.md", "omp.log", "session.txt", "queued", "started", "snapshot.json"):
        (run / stale).unlink(missing_ok=True)
    (QUEUE / "queue").mkdir(parents=True, exist_ok=True)
    ticket = QUEUE / "queue" / f"{time.time_ns()}-{os.getpid()}"
    ticket.write_text(str(run) + "\n")
    (run / "queued").write_text(ticket.name + "\n")
    log = open(run / "launch.log", "w")
    p = subprocess.Popen([sys.executable, str(pathlib.Path(__file__).resolve()), "_run", str(run),
                          "--max-time", a.max_time, "--ticket", str(ticket)],
                         stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    (run / "pid").write_text(str(p.pid))
    print(f"QUEUED: background pid {p.pid}, {ahead(ticket)} run(s) ahead, output in {run.relative_to(root)}/omp.log")
    cmd_wait(a)


def waiting():
    """The queue tickets whose background process is still alive, oldest first; dead ones are dropped."""
    out = []
    for t in sorted((QUEUE / "queue").glob("*")) if (QUEUE / "queue").exists() else []:
        pid_file = pathlib.Path(t.read_text().strip()) / "pid"
        try:
            os.kill(int(pid_file.read_text()), 0)
        except FileNotFoundError:
            pass  # start writes the pid right after the ticket
        except (ValueError, ProcessLookupError, PermissionError):
            t.unlink(missing_ok=True)
            continue
        out.append(t)
    return out


def ahead(ticket):
    """How many runs are queued before `ticket`, plus the one running now."""
    return sum(1 for t in waiting() if t.name < ticket.name) + (1 if running_run() else 0)


def running_run():
    """The run folder that holds the qwen lock now, or None."""
    f = QUEUE / "running"
    if not f.exists():
        return None
    try:
        with open(QUEUE / "qwen.lock", "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh, fcntl.LOCK_UN)
        return None
    except BlockingIOError:
        return f.read_text().strip() or None


def cmd_run(a):
    """The background half of start: wait for the lock, snapshot, run omp, write exit_code."""
    run = pathlib.Path(a.run).resolve()
    ticket = pathlib.Path(a.ticket)
    with open(QUEUE / "qwen.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            ticket.unlink(missing_ok=True)
            (run / "queued").unlink(missing_ok=True)
            (QUEUE / "running").write_text(str(run) + "\n")
            root = ch.repo_root(run)
            ch.snapshot(root, run, {"brief": ch.sha(run / "brief.md")})
            (run / "started").write_text(f"{time.time()}\n")
            rel = run.relative_to(root)
            message = f"Your brief is attached. Do it, then write your report to {rel}/report.md."
            omp = [*NO_CREDENTIALS, "omp", "-p", "--thinking", "xhigh", "--no-title", "--max-time", a.max_time,
                   "--config", str(OVERLAY), "--append-system-prompt", str(RULES),
                   message, f"@{run / 'brief.md'}"]
            (run / "cmd.sh").write_text("#!/bin/bash\n" + f"cd {shlex.quote(str(root))}\n" + shlex.join(omp) + "\n")
            with open(run / "omp.log", "w") as out:
                code = subprocess.run(omp, cwd=root, stdout=out, stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL).returncode
        except Exception as e:  # the run must always end with an exit_code, or `wait` waits forever
            print(f"run failed before omp finished: {e}", file=sys.stderr)
            code = 98
        finally:
            (QUEUE / "running").unlink(missing_ok=True)
        (run / "exit_code").write_text(f"{code}\n")


def cmd_queue(a):
    """List the run that is running and the runs waiting, oldest first."""
    now = running_run()
    print(f"RUNNING: {now or 'none'}")
    for t in waiting():
        print(f"QUEUED:  {t.read_text().strip()}")


def cmd_wait(a):
    """Wait up to --wait seconds, then print the exit code, the session and the report."""
    run = pathlib.Path(a.run).resolve()
    done = run / "exit_code"
    end = float("inf") if a.until_done else time.time() + a.wait
    while time.time() < end and not done.exists():
        time.sleep(5)
    if not done.exists():
        queued = run / "queued"
        if queued.exists() and not (run / "started").exists():
            n = ahead(QUEUE / "queue" / queued.read_text().strip())
            print(f"STATUS: queued, {n} run(s) ahead. Run `offload.py wait {run}` again.")
            return
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


def brief_files(run):
    """The paths under the brief's `## Files you may change`."""
    text = (run / "brief.md").read_text(errors="replace")
    m = re.search(r"^## Files you may change\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return re.findall(r"`([^`]+)`", m.group(1)) if m else []


def omp_written(run, root, snap):
    """Every file the run's omp session edited or wrote, relative to `root`; None when the session is not found."""
    saved = run / "session.txt"
    session = pathlib.Path(saved.read_text().strip()) if saved.exists() else omp_session(root, snap["time"])
    if not session or not session.exists():
        return None
    files = set()

    def walk(x):
        if isinstance(x, dict):
            if x.get("type") == "toolCall" and x.get("name") in ("edit", "write", "multi_edit") \
                    and isinstance(x.get("arguments"), dict) and x["arguments"].get("path"):
                p = pathlib.Path(x["arguments"]["path"])
                p = (p if p.is_absolute() else root / p).resolve()
                try:
                    files.add(str(p.relative_to(root.resolve())))
                except ValueError:
                    pass
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    with open(session, errors="replace") as fh:
        for line in fh:
            try:
                walk(json.loads(line))
            except ValueError:
                continue
    return files


def split_changes(run, root, snap):
    """(qwen's changes, other changes): qwen's are the files its omp session edited or the brief lets it change."""
    changed = ch.changes(root, snap)
    written = omp_written(run, root, snap)
    if written is None:
        return changed, []
    allowed = brief_files(run)
    mine = [(rel, kind) for rel, kind in changed if rel in written or matches(rel, allowed)]
    return mine, [c for c in changed if c not in mine]


def repo_checks(name, path, state):
    """Print one repo's branch, HEAD, stash and remote checks; True when something moved."""
    now = ch.repo_state(path)
    tag = f" [{name}]" if name else ""
    print(f"BRANCH{tag}: {'ok' if now['branch'] == state['branch'] else 'CHANGED'} ({state['branch']} -> {now['branch']})")
    print(f"HEAD{tag}: {'ok' if now['head'] == state['head'] else 'CHANGED'}")
    print(f"STASH{tag}: {'ok' if now['stash'] == state['stash'] else 'CHANGED'}")
    bad = now["branch"] != state["branch"] or now["head"] != state["head"] or now["stash"] != state["stash"]
    if "remotes" in state:
        moved = sorted(r for r in set(now["remotes"]) | set(state["remotes"])
                       if now["remotes"].get(r) != state["remotes"].get(r))
        print(f"REMOTES{tag}: {'ok' if not moved else 'PUSHED ' + ', '.join(moved)}")
        bad |= bool(moved)
    else:
        print(f"REMOTES{tag}: not recorded in this snapshot")
    return bad


def cmd_check(a):
    """Print the free checks, then PASS or FAIL."""
    run, root, snap = ch.load(a.run)
    bad = repo_checks("", root, snap)
    for sub, state in snap.get("repos", {}).items():
        bad |= repo_checks(sub, root / sub, state)
    if ch.sha(run / "brief.md") != snap.get("brief"):
        print("BRIEF: CHANGED by the run")
        bad = True
    lists = risky(root)
    claude_only = lists["claude only"] if lists else []
    changed, other = split_changes(run, root, snap)
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
    if other:
        print(f"OTHER: {len(other)} file(s) changed during the run that qwen's session did not edit and the brief "
              "does not list. Another agent, or qwen through a shell command: read them, they are not counted.")
        for rel, kind in other[:30]:
            print(f"  {kind:8} {rel}")
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
    mine, _ = split_changes(run, root, snap)
    out = []
    for rel, kind in mine:
        if ch.is_binary(root / rel) or ch.is_binary(run / "before" / rel):
            out.append(f"Binary file {rel} {kind}\n")
            continue
        old = ch.before_text(root, run, rel, snap) if kind != "added" else ""
        new = (root / rel).read_text(errors="replace") if kind != "deleted" else ""
        out.extend(ch.difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                           fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        if new and not new.endswith("\n"):
            out.append("\n")
    sys.stdout.write("".join(out))


def cmd_restore(a):
    """Put every protected file qwen touched back, or with --all every file it touched."""
    run, root, snap = ch.load(a.run)
    lists = risky(root)
    claude_only = lists["claude only"] if lists else []
    n = 0
    mine, _ = split_changes(run, root, snap)
    for rel, kind in mine:
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
            t = ch.snapshot_head_text(root, rel, snap)
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
    s.add_argument("--until-done", action="store_true",
                   help="wait with no time limit, for a background shell that ends only when the run does")
    w = sub.add_parser("wait")
    w.add_argument("run")
    w.add_argument("--wait", type=int, default=540)
    w.add_argument("--until-done", action="store_true",
                   help="wait with no time limit, for a background shell that ends only when the run does")
    for name in ("check", "diff"):
        sub.add_parser(name).add_argument("run")
    r = sub.add_parser("restore")
    r.add_argument("run")
    r.add_argument("--all", action="store_true", help="every changed file, for a report-only run")
    sub.add_parser("queue")
    b = sub.add_parser("_run")  # the background half of start; not for direct use
    b.add_argument("run")
    b.add_argument("--max-time", default="60m")
    b.add_argument("--ticket", required=True)
    a = ap.parse_args()
    {"start": cmd_start, "wait": cmd_wait, "check": cmd_check, "diff": cmd_diff,
     "restore": cmd_restore, "queue": cmd_queue, "_run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
