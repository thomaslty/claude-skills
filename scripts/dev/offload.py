#!/usr/bin/env python3
"""Hand one brief to qwen through omp, wait for it, then check what it changed.

Usage:
  offload.py start   <run-dir> [--timeout <duration>]
  offload.py wait    <run-dir>
  offload.py watch   [<run-dir>] [--every 5m]
  offload.py queue
  offload.py check   <run-dir>
  offload.py diff    <run-dir>
  offload.py restore <run-dir> [--all]

<run-dir> is dev/<slug>/offload/<run>/ inside a git repo. Claude writes
brief.md there first. qwen writes report.md there.

start    queues the run and waits until it ends. One qwen run goes at a time
         on this machine; the others wait in ~/.cache/dev-offload/. The
         snapshot is taken when the run's turn comes. There is no time limit
         unless --timeout is given, like 2h: then omp stops the run after that
         long. An agent runs `start` as a background shell and ends its turn:
         it is woken once, when the run ends, and pays nothing while qwen works.
wait     waits until a started run ends, then prints the exit code, qwen's
         report and the omp session to resume. For picking a run back up.
watch    prints how the run is going every 5 minutes, and once right away:
         elapsed, ETA from the brief's files qwen has written, context window,
         prefill and decode speed, and the server's KV cache and load. Each
         block is also a row in progress.md in the run folder. It exits when
         the run ends. With no <run-dir> it follows whichever run is going on
         this machine and never exits. Claude runs it under Monitor, so each
         block wakes it to pass on to you.
queue    the run that is running and the runs waiting, on this machine.
check    the free checks: same branch, HEAD, stash and remote ref of that
         branch in the repo and its submodules, no protected file touched, and whether Claude's
         deep pass is due (.claude/risky.md). Counts as qwen's only the files
         its omp session edited or wrote, plus the brief's `## Files you may
         change`; other files that changed during the run are listed as OTHER.
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
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import changes as ch  # noqa: E402  the shared snapshot and diff

RULES = HERE / "offload-worker-rules.md"
OVERLAY = HERE / "offload-omp.yml"
RISKY_FILE = ".claude/risky.md"
# One local model serves every run. Runs started together slow each other down
# until omp gives up ("Deadline exceeded": 8 of 8 on 2026-11-05), so they queue here.
QUEUE = pathlib.Path(os.environ.get("OFFLOAD_QUEUE_DIR") or pathlib.Path.home() / ".cache" / "dev-offload")  # tests set their own

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
    for stale in ("exit_code", "report.md", "omp.log", "session.txt", "queued", "started", "snapshot.json",
                  "progress.md"):
        (run / stale).unlink(missing_ok=True)
    (QUEUE / "queue").mkdir(parents=True, exist_ok=True)
    ticket = QUEUE / "queue" / f"{time.time_ns()}-{os.getpid()}"
    ticket.write_text(str(run) + "\n")
    (run / "queued").write_text(ticket.name + "\n")
    runner = shlex.join([sys.executable, str(pathlib.Path(__file__).resolve()), "_run", str(run),
                         *(["--timeout", a.timeout] if a.timeout else []), "--ticket", str(ticket)])
    # sh starts the run and exits, so the run belongs to no shell: on 2026-11-05 Claude Code
    # killed an agent's waiting shell and the qwen run under it died, 9 edits in.
    out = subprocess.run(["/bin/sh", "-c", f"{runner} </dev/null >{shlex.quote(str(run / 'launch.log'))} 2>&1 & echo $!"],
                         capture_output=True, text=True, start_new_session=True).stdout.strip()
    (run / "pid").write_text(out)
    print(f"QUEUED: background pid {out}, {ahead(ticket)} run(s) ahead, output in {run.relative_to(root)}/omp.log")
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
            # No limit unless asked: a 60-minute cap cut step 39 off with 2 of 7 files to go.
            limit = ["--max-time", a.timeout] if a.timeout else []
            omp = [*NO_CREDENTIALS, "omp", "-p", "--thinking", "xhigh", "--no-title", *limit,
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


def alive(run):
    """True while the run's background process is still there."""
    try:
        os.kill(int((run / "pid").read_text()), 0)
        return True
    except FileNotFoundError:
        return True  # start writes the pid right after it launches the process
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def cmd_wait(a):
    """Wait until the run ends, then print the exit code, the session and the report."""
    run = pathlib.Path(a.run).resolve()
    done = run / "exit_code"
    while not done.exists():
        if not alive(run):
            time.sleep(2)  # the run may have written exit_code just before it ended
            if not done.exists():
                print("STATUS: stopped without an exit code; its background process is gone. Start it again.")
                return
        time.sleep(5)
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
    """The paths under the brief's `## Files you may change`, with `{a,b}.swift` opened up into one path each."""
    text = (run / "brief.md").read_text(errors="replace")
    m = re.search(r"^## Files you may change\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return [p for g in re.findall(r"`([^`]+)`", m.group(1)) for p in braces(g)] if m else []


def braces(path):
    """`Sources/{Database,LogTailer}.swift` as its two paths; fnmatch cannot read braces."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", path)
    if not m:
        return [path]
    return [p for alt in m.group(1).split(",") for p in braces(path[:m.start()] + alt + path[m.end():])]


def omp_written(run, root, snap):
    """Every file the run's omp session edited or wrote, relative to `root`; None when the session is not found."""
    saved = run / "session.txt"
    session = pathlib.Path(saved.read_text().strip()) if saved.exists() else omp_session(root, snap["time"])
    if not session or not session.exists():
        return None
    return session_writes(session, root)


def session_writes(session, root):
    """Every file an omp session edited or wrote, relative to `root`."""
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
        # Only the branch the run was on counts: a fetch by another session moves the
        # other refs, like origin/dev during the steps 40-41 run on 2026-11-05.
        pushed = [r for r in moved if state["branch"] and r.endswith("/" + state["branch"])]
        print(f"REMOTES{tag}: {'PUSHED ' + ', '.join(pushed) if pushed else 'ok'}"
              + (f" ({len(moved) - len(pushed)} other ref(s) fetched, not counted)" if len(moved) > len(pushed) else ""))
        bad |= bool(pushed)
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


def seconds(text):
    """A duration like 5m, 30s, 1h or 300 as seconds."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smh]?)", text.strip())
    if not m:
        sys.exit(f"--every takes a duration like 5m, not {text}")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def clock(secs):
    """Seconds as 1h 05m, 25m 10s or 40s."""
    secs = int(max(secs, 0))
    h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s" if m else f"{s}s"


def kilo(n):
    """A token count as 950, 12.3k, 500k or 1.2M."""
    for size, unit in ((1e6, "M"), (1e3, "k")):
        if n >= size:
            return f"{n / size:.1f}".removesuffix(".0") + unit
    return f"{n:.0f}"


def turns(session):
    """qwen's finished model turns in an omp session, its model like vllm/qwen3.8-flash-next, and its last message."""
    rows, model, last = [], None, None
    with open(session, errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue  # omp may be halfway through writing the last line
            if d.get("type") == "model_change":
                model = d.get("model")
            m = d.get("message")
            if d.get("type") != "message" or not isinstance(m, dict):
                continue
            content = m.get("content") if isinstance(m.get("content"), list) else []
            calls = [c.get("name") for c in content if isinstance(c, dict) and c.get("type") == "toolCall"]
            last = (m.get("role"), ts(d.get("timestamp")), calls)
            u = m.get("usage")
            if m.get("role") != "assistant" or not isinstance(u, dict):
                continue
            ttft = (m.get("ttft") or 0) / 1000
            prompt = (m.get("contextSnapshot") or {}).get("promptTokens") or u.get("input", 0) + u.get("cacheRead", 0)
            rows.append({"end": ts(d.get("timestamp")), "new": u.get("input", 0), "cached": u.get("cacheRead", 0),
                         "out": u.get("output", 0), "think": u.get("reasoningTokens") or 0, "ttft": ttft,
                         "decode": max((m.get("duration") or 0) / 1000 - ttft, 0),
                         "context": prompt + u.get("output", 0)})
    return rows, model, last


def speeds(rows, span):
    """The speed table's cells for some turns: prefill, decode, tokens out, thinking, cache hit, turns, model busy."""
    if not rows:
        return ["-"] * 7
    new, cached, out, think = (sum(r[f] for r in rows) for f in ("new", "cached", "out", "think"))
    ttft, decode = sum(r["ttft"] for r in rows), sum(r["decode"] for r in rows)
    return [f"{new / ttft:,.0f}" if ttft else "-", f"{out / decode:.1f}" if decode else "-", kilo(out),
            f"{think / out:.0%}" if out else "-", f"{cached / (new + cached):.0%}" if new + cached else "-",
            str(len(rows)), f"{min((ttft + decode) / span, 1):.0%}" if span else "-"]


def http(url, key):
    """The body at `url`, or None when it does not answer in 5 seconds."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode(errors="replace")
    except Exception:
        return None


def model_server(model):
    """omp's base URL, API key, model name and context window for `model`, like vllm/qwen3.8-flash-next."""
    provider, _, name = (model or "").partition("/")
    try:
        import yaml
        conf = yaml.safe_load((pathlib.Path.home() / ".omp/agent/models.yml").read_text())["providers"][provider]
    except Exception:
        return None
    key = conf.get("apiKey")
    key = os.environ.get(key, key) if key else None  # omp takes an env var name or the key itself
    base = (conf.get("baseUrl") or "").rstrip("/")
    try:
        window = next(d.get("max_model_len") for d in json.loads(http(base + "/models", key))["data"] if d["id"] == name)
    except Exception:
        window = None
    return {"base": base, "key": key, "name": name, "window": window}


def vllm(srv):
    """vLLM's gauges and counters for the model, summed over its engines; {} when /metrics does not answer."""
    text = http(re.sub(r"/v1$", "", srv["base"]) + "/metrics", srv["key"]) or ""
    out = {}
    for line in text.splitlines():
        m = re.match(r"(vllm:\w+)\{([^}]*)\} (\S+)$", line)
        if m and f'model_name="{srv["name"]}"' in m.group(2) and "le=" not in m.group(2):
            out[m.group(1)] = out.get(m.group(1), 0) + float(m.group(3))
    if out:
        out["t"] = time.time()
    return out


def run_times(run):
    """When the run started and its snapshot, or (None, None) before its turn has come."""
    snap_file = run / "snapshot.json"
    if not snap_file.exists():
        return None, None
    snap = json.loads(snap_file.read_text())
    started = run / "started"
    return (float(started.read_text()) if started.exists() else snap["time"]), snap


def label(run):
    """The repo's folder name, like `tg-spark-tailscale-proxy`, from <repo>/dev/<slug>/offload/<run>."""
    return run.parents[3].name


def progress(run, every, cache):
    """One progress block for a run, as markdown, and the row it adds to progress.md."""
    name = label(run)
    now = time.time()
    started, snap = run_times(run)
    if started is None:
        queued = run / "queued"
        ticket = QUEUE / "queue" / queued.read_text().strip() if queued.exists() else None
        if ticket:
            return f"qwen {name} · queued {clock(now - int(ticket.name.split('-')[0]) / 1e9)}, " \
                   f"{ahead(ticket)} run(s) ahead", None
        return f"qwen {name} · waiting for its turn", None
    elapsed = now - started
    root = pathlib.Path(snap["root"])
    session = omp_session(root, snap["time"])
    if not session:
        return f"qwen {name} · running {clock(elapsed)} · omp is starting, no model turn yet", None
    rows, model, last = turns(session)

    allowed = brief_files(run)
    written = session_writes(session, root)
    done = sum(1 for f in allowed if any(matches(w, [f]) for w in written))
    if not allowed:
        eta = "no ETA, the brief lists no files"
    elif not done:
        eta = f"files 0/{len(allowed)} · ETA after the first file"
    elif done < len(allowed):
        eta = f"files {done}/{len(allowed)} · ETA ~{clock(elapsed / done * (len(allowed) - done))}"
    else:
        eta = f"files {done}/{len(allowed)} · all written, qwen is checking its work"

    if model not in cache:
        cache[model] = model_server(model)
    srv = cache[model]
    live = ""
    a = vllm(srv) if srv else {}
    if a:
        time.sleep(3)
        b = vllm(srv)
        if b:
            rate = (b["vllm:generation_tokens_total"] - a["vllm:generation_tokens_total"]) / (b["t"] - a["t"])
            live = f", {rate:.0f} tok/s now"
            a = b
    role, at, calls = last or (None, started, [])
    if role == "assistant" and calls:
        doing = f"running {', '.join(calls)} for {clock(now - at)}"
    elif role == "assistant":
        doing = "done, omp is closing"
    else:
        doing = f"model turn {len(rows) + 1} for {clock(now - at)}{live}"

    state = []
    if rows:
        ctx = rows[-1]["context"]
        window = srv and srv["window"]
        state.append(f"context {kilo(ctx)} / {kilo(window)} ({ctx / window:.0%})" if window else f"context {kilo(ctx)}")
    if a:
        state.append(f"KV cache {a.get('vllm:kv_cache_usage_perc', 0):.0%}")
        state.append(f"server {a.get('vllm:num_requests_running', 0):.0f} running, "
                     f"{a.get('vllm:num_requests_waiting', 0):.0f} waiting")
    elif srv:
        state.append("server metrics not answering")
    queued = len(waiting())
    if queued:
        state.append(f"{queued} run(s) queued after it")

    recent = speeds([r for r in rows if r["end"] >= now - every], every)
    whole = speeds(rows, elapsed)
    span = clock(every).replace("m 00s", "m")
    labels = ["prefill tok/s", "decode tok/s", "tokens out", "thinking", "cache hit", "model turns", "model busy"]
    lines = [f"qwen {name} · running {clock(elapsed)} · {eta}", f"now: {doing}", " · ".join(state), "",
             f"| speed | last {span} | whole run |", "|---|---|---|"]
    lines += [f"| {label} | {x} | {y} |" for label, x, y in zip(labels, recent, whole)]
    ctx_cell = kilo(rows[-1]["context"]) if rows else "-"
    row = (f"| {time.strftime('%H:%M')} | {clock(elapsed)} | {done}/{len(allowed)} | {ctx_cell} | "
           f"{whole[0]} | {whole[1]} | {recent[1]} | {whole[2]} | {whole[5]} |")
    return "\n".join(lines), row


def log_progress(run, row):
    """Add one row to progress.md in the run folder, with the header the first time."""
    f = run / "progress.md"
    head = "" if f.exists() else ("| time | elapsed | files | context | prefill tok/s | decode tok/s | "
                                  "decode last tick | tokens out | turns |\n|---|---|---|---|---|---|---|---|---|\n")
    with open(f, "a") as fh:
        fh.write(head + row + "\n")


def ended(run):
    """The last line for a run that is over."""
    name = label(run)
    code_file = run / "exit_code"
    for _ in range(10):  # the run lets go of the lock a moment before it writes exit_code
        if code_file.exists() or not alive(run):
            break
        time.sleep(1)
    if not code_file.exists():
        return f"qwen {name} stopped without an exit code; its background process is gone"
    started, snap = run_times(run)
    took = f" after {clock(code_file.stat().st_mtime - started)}" if started else ""
    log = run / "progress.md"
    if log.exists() and log.is_relative_to(snap["root"]):
        log = log.relative_to(snap["root"])
    tail = f" · every tick is in {log}" if (run / "progress.md").exists() else ""
    return f"qwen {name} ended: exit {code_file.read_text().strip()}{took}{tail}"


def cmd_watch(a):
    """Print a progress block every --every until the run ends; with no run, follow whichever run is going."""
    every = seconds(a.every)
    cache, cur, next_at, shown = {}, None, 0, 0
    fixed = pathlib.Path(a.run).resolve() if a.run else None
    while True:
        if fixed:
            now_run = None if (fixed / "exit_code").exists() or not alive(fixed) else fixed
        else:
            r = running_run()
            now_run = pathlib.Path(r) if r else None
        if cur and now_run != cur:
            print(ended(cur), flush=True)
            cur = None
        if fixed and now_run is None:
            if not shown:
                print(ended(fixed), flush=True)
            return
        if now_run and now_run != cur:
            cur, next_at, shown = now_run, 0, 0
        if cur and time.time() >= next_at:
            try:
                block, row = progress(cur, every, cache)
                if row:
                    log_progress(cur, row)
            except Exception as e:  # one bad read must not end the watch
                block, row = f"qwen {label(cur)}: could not read its progress this time ({e})", True
            # Before omp's first turn, look again in 15 seconds, but say so only once per tick.
            if row or time.time() - shown >= every:
                print(block + "\n", flush=True)
                shown = time.time()
            next_at = time.time() + (every if row else 15)
        time.sleep(5)


def main():
    """Run one of the commands."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("run")
    s.add_argument("--timeout", default=None, help="stop the run after this long, like 2h; no limit by default")
    sub.add_parser("wait").add_argument("run")
    w = sub.add_parser("watch")
    w.add_argument("run", nargs="?", help="the run to watch; none follows whichever run is going on this machine")
    w.add_argument("--every", default="5m", help="how often to print, like 5m or 30s")
    for name in ("check", "diff"):
        sub.add_parser(name).add_argument("run")
    r = sub.add_parser("restore")
    r.add_argument("run")
    r.add_argument("--all", action="store_true", help="every changed file, for a report-only run")
    sub.add_parser("queue")
    b = sub.add_parser("_run")  # the background half of start; not for direct use
    b.add_argument("run")
    b.add_argument("--timeout", default=None)
    b.add_argument("--ticket", required=True)
    a = ap.parse_args()
    {"start": cmd_start, "wait": cmd_wait, "watch": cmd_watch, "check": cmd_check, "diff": cmd_diff,
     "restore": cmd_restore, "queue": cmd_queue, "_run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
