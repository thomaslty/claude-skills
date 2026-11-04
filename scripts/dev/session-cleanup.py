#!/usr/bin/env python3
"""Find what this Claude Code session started and left running, and stop it.

Usage:
  session-cleanup.py                 list it as JSON, changes nothing
  session-cleanup.py stop ID...      stop those IDs
  session-cleanup.py stop --sure     stop every item with "sure": true
  session-cleanup.py stop --all      stop every item

stop looks again first, so an ID that is gone or no longer matches does nothing.

It covers processes (a bash script, a server like uvicorn or vite, anything holding a
port), docker containers, compose projects, and colima when this session started it.
It knows the session from $CLAUDE_CODE_SESSION_ID and $CLAUDE_PID, which Claude Code
sets in every Bash call, and reads the commands the session ran from its transcript.

"sure": true   runs under this Claude, or a command of this session started it
"sure": false  only a loose match, like the same port or the same minute, you have to check
"""
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

HOME = os.path.expanduser("~")
NOW = time.time()
SHELLS = {"zsh", "bash", "sh", "dash", "fish"}
# argv words too common to tie a process to one command
COMMON = {"bin", "usr", "local", "env", "exec", "run", "node", "npm", "npx", "java", "ruby",
          "uv", "uvx", "true", "127.0.0.1", "0.0.0.0", "localhost", "nohup", "opt", "homebrew"}
INTERPRETERS = re.compile(r"(python[\d.]*|node|ruby|bun|deno|perl)")
DOCKER_START = re.compile(r"\bdocker(?:-compose|\s+compose)?\b[^;&|\n]*?\b(?:up|run|create|start|restart)\b")
PORT_WORD = re.compile(r"(?:[:=]|\bport\s*[=\s]\s*|-p\s+|--port\s+)(\d{4,5})\b", re.I)
CD = re.compile(r"(?:^|[;&|({\n]\s*)cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|)]+)")
YML = re.compile(r"(\"[^\"]+\.ya?ml\"|'[^']+\.ya?ml'|[^\s\"';&|=]+\.ya?ml)\b")
SYSTEM = re.compile(r"\.app/Contents/|^/System/|^/usr/libexec/|^/usr/sbin/|^/sbin/|^/Library/")
COLIMA = re.compile(r"limactl|/\.colima/|/\.lima/|\bcolima\b")
SKEW = 30  # seconds the colima VM clock may be off from the Mac's


def sh(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LC_ALL": "C"})
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def epoch(ts):
    try:
        return datetime.fromisoformat(re.sub(r"\.\d+", "", ts).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def hm(t):
    fmt = "%H:%M" if time.strftime("%Y%m%d", time.localtime(t)) == time.strftime("%Y%m%d") else "%b %d %H:%M"
    return time.strftime(fmt, time.localtime(t))


def short(s, n=30):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


# ---------- processes ----------

def processes():
    _, out, _ = sh(["ps", "-axww", "-o", "pid=,ppid=,pgid=,uid=,stat=,lstart=,command="])
    procs = {}
    for line in out.splitlines():
        f = line.split(None, 10)
        if len(f) < 11:
            continue
        try:
            start = time.mktime(time.strptime(" ".join(f[5:10]), "%a %b %d %H:%M:%S %Y"))
        except ValueError:
            continue
        procs[int(f[0])] = {"pid": int(f[0]), "ppid": int(f[1]), "pgid": int(f[2]), "uid": int(f[3]),
                            "stat": f[4], "start": start, "cmd": f[10]}
    return procs


def subtree(root, kids):
    out, todo = [], [root]
    while todo:
        p = todo.pop(0)
        out.append(p)
        todo.extend(kids.get(p, []))
    return out


def listeners():
    _, out, _ = sh(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn"], timeout=20)
    ports, pid = {}, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid:
            port = line.rsplit(":", 1)[-1]
            if port.isdigit():
                ports.setdefault(pid, set()).add(int(port))
    return ports


def cwds(pids):
    if not pids:
        return {}
    _, out, _ = sh(["lsof", "-a", "-d", "cwd", "-Fpn", "-p", ",".join(map(str, pids))])
    res, pid = {}, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid:
            res[pid] = line[1:]
    return res


def find_claude(procs):
    env = os.environ.get("CLAUDE_PID", "")
    if env.isdigit() and int(env) in procs:
        return int(env)
    p = os.getppid()
    while p > 1 and p in procs:
        argv0 = (procs[p]["cmd"].split() or [""])[0]
        if os.path.basename(argv0) == "claude" or "/claude/versions/" in argv0:
            return p
        p = procs[p]["ppid"]
    return None


def chain(pid, procs):
    out = []
    while pid > 1 and pid in procs and pid not in out:
        out.append(pid)
        pid = procs[pid]["ppid"]
    return out


def label(cmd):
    argv = cmd.split()
    if not argv:
        return cmd
    head, rest = os.path.basename(argv[0]), argv[1:]
    if INTERPRETERS.fullmatch(head) and rest and not rest[0].startswith("-"):
        head, rest = os.path.basename(rest[0]), rest[1:]
    return " ".join([head] + rest)


def original_command(shell_cmd):
    m = re.search(r"eval '(.*?)' < /dev/null", shell_cmd, re.S)
    if not m:
        return None
    return m.group(1).replace("'\\''", "'").replace("\\012", "\n")


def strip_cd(cmd):
    first = cmd.strip().splitlines()[0] if cmd.strip() else cmd
    return re.sub(r"^(?:\s*cd\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s*&&\s*)+", "", first)


# ---------- transcript ----------

def expand(text):
    text = re.sub(r"\$\{?HOME\}?", HOME, text)
    return re.sub(r"(^|[\s='\"(:])~(?=/)", lambda m: m.group(1) + HOME, text)


def resolve(path, base):
    return os.path.normpath(os.path.join(base, os.path.expanduser(path.strip("'\""))))


def transcript_files(session):
    for base in filter(None, [os.environ.get("CLAUDE_CONFIG_DIR"), os.path.join(HOME, ".claude")]):
        hits = glob.glob(os.path.join(base, "projects", "*", session + ".jsonl"))
        if hits:
            return [hits[0]] + sorted(glob.glob(os.path.join(hits[0][:-6], "subagents", "*.jsonl")))
    return []


def load_calls(files):
    calls, ends, first = {}, {}, None
    for n, path in enumerate(files):
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or not rec.get("timestamp"):
                    continue
                t = epoch(rec["timestamp"])
                if n == 0 and t:
                    first = t if first is None else min(first, t)
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        cmd = (b.get("input") or {}).get("command")
                        if isinstance(cmd, str) and b.get("id") not in calls:
                            calls[b["id"]] = {"start": t, "cwd": rec.get("cwd") or HOME, "cmd": cmd,
                                              "bg": bool(b["input"].get("run_in_background"))}
                    elif b.get("type") == "tool_result":
                        ends.setdefault(b.get("tool_use_id"), t)
                        res = rec.get("toolUseResult")
                        if isinstance(res, dict) and res.get("backgroundTaskId") and b.get("tool_use_id") in calls:
                            calls[b["tool_use_id"]]["bg"] = True
    out = []
    for cid, c in calls.items():
        c["end"] = ends.get(cid, NOW)
        c["text"] = expand(c["cmd"])
        dirs, base = [c["cwd"]], c["cwd"]
        for m in CD.finditer(c["text"]):
            base = resolve(m.group(1), base)
            dirs.append(base)
        files = {resolve(m.group(1), d) for m in YML.finditer(c["text"]) for d in dirs}
        c["dirs"] = set(dirs) | {os.path.dirname(f) for f in files}
        c["files"] = files
        c["ports"] = {int(p) for p in PORT_WORD.findall(c["text"])}
        out.append(c)
    return first, out


def hit(token, text):
    return bool(token) and re.search(r"(?<![\w.-])" + re.escape(token) + r"(?![\w/-])", text) is not None


def arg_forms(cmd):
    forms = []
    for a in cmd.split():
        if a.startswith("-"):
            if "=" not in a:
                continue
            a = a.split("=", 1)[1]
        f = {t for t in (a, os.path.basename(a.rstrip("/")))
             if len(t) >= 3 and t.lower() not in COMMON and not re.fullmatch(r"python[\d.]*", t, re.I)}
        if f:
            forms.append(f)
    return forms


def in_window(t, call, after=3):
    return call["start"] - 2 <= t <= call["end"] + (60 if call["bg"] else after)


# ---------- discovery ----------

def discover():
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    procs = processes()
    claude = find_claude(procs)
    if not session or not claude:
        return {"error": "run this from a Bash call inside Claude Code; $CLAUDE_CODE_SESSION_ID or the claude process is missing"}

    files = transcript_files(session)
    first, calls = load_calls(files)
    start = min(filter(None, [first, procs[claude]["start"]]))
    kids = {}
    for p in procs.values():
        kids.setdefault(p["ppid"], []).append(p["pid"])
    ports = listeners()
    me = os.getuid()
    own = set(chain(os.getpid(), procs))
    items = []

    def ports_of(pids):
        return sorted({port for p in pids for port in ports.get(p, ())})

    def main_proc(pids):
        real = [p for p in pids if os.path.basename((procs[p]["cmd"].split() or [""])[0]) not in SHELLS]
        with_port = [p for p in real if p in ports]
        return (with_port or real or pids)[0]

    # 1. under this Claude, through a Bash-tool shell: a background task, or a call still running
    for sh_pid in kids.get(claude, []):
        p = procs[sh_pid]
        argv0 = os.path.basename((p["cmd"].split() or [""])[0])
        if sh_pid in own or argv0 not in SHELLS or "shell-snapshots" not in p["cmd"]:
            continue
        pids = subtree(sh_pid, kids)
        cmd = original_command(p["cmd"]) or procs[main_proc(pids)]["cmd"]
        items.append({"id": f"p{sh_pid}", "kind": "process", "sure": True,
                      "what": short(strip_cd(cmd)), "ports": ports_of(pids), "started": hm(p["start"]),
                      "why": "runs under this Claude", "command": cmd[:400], "pids": pids})
    taken = {p for i in items for p in i["pids"]}

    # 2. left behind: a process a call started with & or nohup, now parented to launchd
    roots = [p for p in procs.values()
             if p["ppid"] == 1 and p["uid"] == me and p["start"] >= start - 2 and p["pid"] not in taken
             and not SYSTEM.search(p["cmd"]) and not COLIMA.search(p["cmd"])]
    dirs = cwds([p["pid"] for p in roots])
    for p in roots:
        pids = subtree(p["pid"], kids)
        pports = ports_of(pids)
        forms = arg_forms(p["cmd"])
        sure, why = None, None
        for c in calls:
            matched = sum(1 for f in forms if any(hit(t, c["text"]) for t in f))
            if in_window(p["start"], c) and (matched or dirs.get(p["pid"]) in c["dirs"]):
                sure, why = True, f"your call at {hm(c['start'])}"
                break
            if sure is None and (matched >= 2 or set(pports) & c["ports"]):
                sure, why = False, "port named in a call" if set(pports) & c["ports"] else "looks like a call"
        if sure is None:
            continue
        items.append({"id": f"p{p['pid']}", "kind": "process", "sure": sure,
                      "what": short(label(procs[main_proc(pids)]["cmd"])), "ports": pports,
                      "started": hm(p["start"]), "why": why, "command": p["cmd"][:400], "pids": pids})

    # 3. docker containers and compose projects
    docker, containers = docker_state()
    linked = []
    for c in containers:
        link = container_link(c, calls, start)
        if link:
            linked.append((c, *link))
    by_project = {}
    for c, sure, why in linked:
        if c["project"]:
            by_project.setdefault(c["project"], []).append((c, sure, why))
    whole = {p for p, members in by_project.items()
             if len(members) == sum(1 for c in containers if c["project"] == p)}
    for project in sorted(whole):
        members = by_project[project]
        items.append({"id": f"compose:{project}", "kind": "compose", "sure": all(s for _, s, _ in members),
                      "what": short(f"compose {project} ({len(members)})"),
                      "ports": sorted({x for c, _, _ in members for x in c["ports"]}),
                      "started": hm(min(c["created"] for c, _, _ in members)), "why": members[0][2],
                      "command": f"docker compose -p {project} down",
                      "containers": [c["name"] for c, _, _ in members]})
    for c, sure, why in linked:
        if c["project"] in whole:
            continue
        items.append({"id": f"c{c['id'][:12]}", "kind": "container", "sure": sure, "what": short(c["name"]),
                      "ports": c["ports"], "started": hm(c["created"]), "why": why,
                      "command": f"docker rm -f {c['name']}", "state": c["state"]})

    # 4. colima, only when this session started it and nothing else runs in it
    ours = {c["id"] for c, _, _ in linked}
    others = [c for c in containers if c["state"] == "running" and c["id"] not in ours]
    if docker == "ok" and not others:
        for p in procs.values():
            m = re.search(r"limactl hostagent .*?/_lima/(colima(?:-[\w.-]+)?)/", p["cmd"])
            if not m or p["start"] < start - 2:
                continue
            said = any(re.search(r"\bcolima\s+start\b", c["text"]) for c in calls)
            during = any(in_window(p["start"], c, after=60) for c in calls)
            if said or during:
                profile = m.group(1)[len("colima-"):] if "-" in m.group(1) else ""
                items.append({"id": f"colima:{profile or 'default'}", "kind": "colima", "sure": said,
                              "what": f"colima {profile or 'VM'}", "ports": [], "started": hm(p["start"]),
                              "why": "colima start in a call" if said else "started during a call",
                              "command": "colima stop" + (f" -p {profile}" if profile else "")})

    return {"session": session, "since": hm(start), "transcript": files[0] if files else None,
            "docker": docker, "items": items}


def docker_state():
    if not shutil.which("docker"):
        return "not installed", []
    rc, out, _ = sh(["docker", "ps", "-aq", "--no-trunc"], timeout=10)
    if rc != 0:
        return "not running", []
    ids = out.split()
    if not ids:
        return "ok", []
    _, out, _ = sh(["docker", "inspect", *ids], timeout=30)
    try:
        data = json.loads(out or "[]")
    except ValueError:
        data = []
    res = []
    for c in data:
        cfg = c.get("Config") or {}
        labels = cfg.get("Labels") or {}
        ports = {int(b["HostPort"]) for binds in ((c.get("NetworkSettings") or {}).get("Ports") or {}).values()
                 for b in binds or [] if str(b.get("HostPort", "")).isdigit()}
        res.append({"id": c["Id"], "name": c.get("Name", "").lstrip("/"), "image": cfg.get("Image", ""),
                    "created": epoch(c.get("Created")), "state": (c.get("State") or {}).get("Status", ""),
                    "project": labels.get("com.docker.compose.project"),
                    "workdir": labels.get("com.docker.compose.project.working_dir") or "",
                    "configs": [f for f in (labels.get("com.docker.compose.project.config_files") or "").split(",") if f],
                    "ports": sorted(ports)})
    return "ok", res


def container_link(c, calls, start):
    if c["created"] < start - SKEW:
        return None
    image = re.sub(r"[:@].*$", "", c["image"])
    started, during, maybe = None, None, None
    for k in calls:
        text = k["text"]
        named = hit(c["name"], text) or c["id"][:12] in text or bool(
            c["project"] and re.search(r"(?:-p|--project-name)[\s=]+['\"]?" + re.escape(c["project"]) + r"\b", text))
        composed = bool(c["project"] and "compose" in text
                        and (c["workdir"] in k["dirs"] or any(f in k["files"] for f in c["configs"])))
        loose = (c["workdir"] and c["workdir"] in text) or any(f in text for f in c["configs"]) or (
            len(image) >= 4 and hit(image, text))
        window = k["start"] - SKEW <= c["created"] <= k["end"] + (600 if k["bg"] else SKEW)
        if (named or composed) and DOCKER_START.search(text) and not started:
            started = (True, f"your call at {hm(k['start'])}")
        if (named or composed or loose) and window and not during:
            during = (True, f"made during call {hm(k['start'])}")
        if not k["bg"] and k["end"] - k["start"] >= 1 and k["start"] - 10 <= c["created"] <= k["end"] + 10:
            maybe = (False, "same time as a call")
    return started or during or maybe


# ---------- stop ----------

def alive(pids):
    if not pids:
        return []
    _, out, _ = sh(["ps", "-o", "pid=,stat=", "-p", ",".join(map(str, pids))])
    return [int(f[0]) for f in (l.split() for l in out.splitlines()) if len(f) == 2 and not f[1].startswith("Z")]


def kill_tree(pids):
    procs = processes()
    claude = find_claude(procs)
    guard = {1, claude} | set(chain(os.getpid(), procs))
    pids = [p for p in pids if p not in guard and procs.get(p, {}).get("uid") == os.getuid()]
    guard_groups = {procs[claude]["pgid"] if claude in procs else -1, os.getpgid(0)}
    for g in {procs[p]["pgid"] for p in pids} - guard_groups:
        if {q for q, v in procs.items() if v["pgid"] == g} <= set(pids):
            try:
                os.killpg(g, signal.SIGTERM)
            except OSError:
                pass
    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5
    while time.time() < deadline and alive(pids):
        time.sleep(0.2)
    left = alive(pids)
    for p in left:
        try:
            os.kill(p, signal.SIGKILL)
        except OSError:
            pass
    if left:
        time.sleep(0.5)
        left = alive(pids)
    return (not left, "stopped" if not left else f"still running: {left}")


def stop(args):
    found = discover()
    if "error" in found:
        return found
    items = found["items"]
    pick = [i for i in items if "--all" in args or ("--sure" in args and i["sure"]) or i["id"] in args]
    order = {"process": 0, "container": 1, "compose": 2, "colima": 3}
    results = []
    for i in sorted(pick, key=lambda i: order[i["kind"]]):
        if i["kind"] == "process":
            ok, detail = kill_tree(i["pids"])
        elif i["kind"] == "container":
            rc, _, err = sh(["docker", "rm", "-f", i["id"][1:]], timeout=60)
            ok, detail = rc == 0, "removed" if rc == 0 else short(err.strip(), 80)
        elif i["kind"] == "compose":
            rc, _, err = sh(["docker", "compose", "-p", i["id"].split(":", 1)[1], "down"], timeout=120)
            ok, detail = rc == 0, "down, volumes kept" if rc == 0 else short(err.strip(), 80)
        else:
            _, running, _ = sh(["docker", "ps", "-q"], timeout=10)
            if running.strip():
                ok, detail = False, "kept, other containers run in it"
            else:
                rc, _, err = sh(i["command"].split(), timeout=180)
                ok, detail = rc == 0, "stopped" if rc == 0 else short(err.strip(), 80)
        results.append({"id": i["id"], "what": i["what"], "ok": ok, "detail": detail})
    known = {i["id"] for i in items}
    for a in args:
        if not a.startswith("--") and a not in known:
            results.append({"id": a, "what": "", "ok": False, "detail": "gone, or not from this session"})
    still = [i for i in discover().get("items", []) if i["id"] in {r["id"] for r in results}]
    return {"results": results, "still_running": [i["id"] for i in still],
            "ports_still_open": sorted({p for i in still for p in i["ports"]})}


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if args and args[0] == "stop":
        if len(args) == 1:
            sys.exit("stop needs IDs, --sure or --all\n\n" + __doc__)
        print(json.dumps(stop(args[1:]), indent=1))
    elif not args:
        print(json.dumps({k: v for k, v in discover().items()}, indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
