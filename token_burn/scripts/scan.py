"""Scan every Claude Code session log and write per-file token facts to a JSON file."""
import json, os, re, sys, glob, collections
from multiprocessing import Pool

ROOT = os.path.expanduser('~/.claude/projects')
IMG_CHARS = 6000  # one image is about 1.5k tokens, counted as 6000 chars


def tool_cat(name):
    if not name:
        return 'tool:?'
    if name.startswith('mcp__'):
        parts = name.split('__')
        return 'mcp:' + (parts[1] if len(parts) > 1 else name)
    return 'tool:' + name


def blk_chars(c):
    """chars and image count of a tool_result content field"""
    if isinstance(c, str):
        return len(c), 0
    n = img = 0
    if isinstance(c, list):
        for b in c:
            if not isinstance(b, dict):
                continue
            t = b.get('type')
            if t == 'text':
                n += len(b.get('text') or '')
            elif t == 'image':
                img += 1
            else:
                n += len(json.dumps(b))
    return n, img


def shape_summary(shape):
    sysc = sum(len(b.get('text', '')) for b in shape.get('system', []))
    g = collections.Counter()
    for t in shape.get('tools', []):
        n = t.get('name', '?')
        if n.startswith('mcp__'):
            key = 'mcp:' + n.split('__')[1]
        elif t.get('defer_loading'):
            key = 'deferred'
        else:
            key = 'builtin:' + n
        g[key] += len(json.dumps(t))
    return {'system': sysc, 'tools': dict(g)}


def scan(path):
    rel = os.path.relpath(path, ROOT)
    parts = rel.split(os.sep)
    project = parts[0]
    sub = 'subagents' in parts
    session = parts[1] if sub else parts[1][:-6]
    agent_type = None
    if sub:
        meta = path[:-6] + '.meta.json'
        try:
            agent_type = json.load(open(meta)).get('agentType')
        except Exception:
            pass
    out = dict(path=rel, project=project, session=session, sub=sub, agent_type=agent_type,
               mtime=os.path.getmtime(path), size=os.path.getsize(path))
    calls = {}            # msg_id -> row
    order = []
    req_src = {}          # api-request id -> (querySource, effort)
    shapes = {}
    resident = collections.Counter()
    resid = collections.Counter()   # category -> char-calls
    added = collections.Counter()   # category -> chars added
    cnt = collections.Counter()     # category -> number of items
    tool_names = {}
    uses = collections.Counter()
    first_blocks = None
    cost_state = None
    compactions = 0
    big_results = []                # (chars, category, preview)

    def add(cat, n, preview=None):
        if n <= 0:
            return
        resident[cat] += n
        added[cat] += n
        cnt[cat] += 1
        if preview is not None and n >= 40000:
            big_results.append((n, cat, preview[:160]))

    with open(path, 'rb') as fh:
        for line in fh:
            head = line[:60]
            if b'api-request-blob' in head:
                continue
            if b'"type":"api-request-shape"' in head:
                try:
                    d = json.loads(line)
                    if d['shapeHash'] not in shapes:
                        shapes[d['shapeHash']] = shape_summary(d['shape'])
                except Exception:
                    pass
                continue
            if b'"type":"api-request"' in head:
                try:
                    d = json.loads(line)
                    req_src[d['id']] = (d.get('querySource'), (d.get('params') or {}).get('output_config', {}).get('effort'),
                                        d.get('shapeHash'))
                except Exception:
                    pass
                continue
            if b'"type":"cost-state"' in head:
                try:
                    cost_state = json.loads(line)
                except Exception:
                    pass
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get('type')
            if t == 'assistant':
                m = d.get('message') or {}
                mid = m.get('id') or d.get('requestId') or d.get('uuid')
                u = m.get('usage') or {}
                if mid not in calls:
                    # a new API call: everything resident is read again
                    for k, v in resident.items():
                        resid[k] += v
                    order.append(mid)
                    calls[mid] = None
                cc = u.get('cache_creation') or {}
                cc5 = cc.get('ephemeral_5m_input_tokens')
                cc1 = cc.get('ephemeral_1h_input_tokens')
                cct = u.get('cache_creation_input_tokens') or 0
                if cc5 is None and cc1 is None:
                    cc5, cc1 = cct, 0
                row = (m.get('model'), d.get('timestamp'), u.get('input_tokens') or 0, cc5 or 0, cc1 or 0,
                       u.get('cache_read_input_tokens') or 0, u.get('output_tokens') or 0,
                       (u.get('output_tokens_details') or {}).get('thinking_tokens') or 0,
                       d.get('effort'), d.get('requestRef'), d.get('isSidechain'))
                prev = calls.get(mid)
                if prev is None or row[6] >= prev[6]:
                    calls[mid] = row
                for b in m.get('content') or []:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get('type')
                    if bt == 'text':
                        add('assistant:text', len(b.get('text') or ''))
                    elif bt == 'tool_use':
                        nm = b.get('name')
                        tool_names[b.get('id')] = nm
                        inp = b.get('input') or {}
                        add('assistant:tool_input', len(json.dumps(inp)))
                        uses['tool:' + str(nm)] += 1
                        if nm == 'Skill':
                            uses['skill:' + str(inp.get('skill'))] += 1
                        elif nm in ('Agent', 'Task'):
                            uses['agent:' + str(inp.get('subagent_type') or 'general-purpose')] += 1
            elif t == 'user':
                m = d.get('message') or {}
                c = m.get('content')
                if d.get('isCompactSummary'):
                    cat = 'user:compact_summary'
                elif d.get('isMeta'):
                    cat = 'user:meta'
                else:
                    cat = 'user:prompt'
                if isinstance(c, str):
                    add(cat, len(c))
                    for cmd in re.findall(r'<command-name>/?([^<]+)</command-name>', c):
                        uses['cmd:' + cmd.strip()] += 1
                elif isinstance(c, list):
                    for b in c:
                        if not isinstance(b, dict):
                            continue
                        bt = b.get('type')
                        if bt == 'tool_result':
                            nm = tool_names.get(b.get('tool_use_id'))
                            n, img = blk_chars(b.get('content'))
                            tc = tool_cat(nm)
                            prev = b.get('content') if isinstance(b.get('content'), str) else json.dumps(b.get('content'))[:300]
                            add(tc, n, preview=(str(nm) + ' | ' + (prev or '')))
                            if img:
                                add('image:' + tc, img * IMG_CHARS)
                        elif bt == 'text':
                            tx = b.get('text') or ''
                            add(cat, len(tx))
                            for cmd in re.findall(r'<command-name>/?([^<]+)</command-name>', tx):
                                uses['cmd:' + cmd.strip()] += 1
                        elif bt == 'image':
                            add('image:user', IMG_CHARS)
                        else:
                            add(cat, len(json.dumps(b)))
            elif t == 'attachment':
                a = d.get('attachment') or {}
                at = a.get('type', '?')
                if at in ('hook_success', 'hook_additional_context', 'hook_non_blocking_error', 'hook_blocking_error'):
                    hn = a.get('hookName') or a.get('hookEvent') or '?'
                    at = at + ':' + hn
                n = len(json.dumps(a.get('content'))) if 'content' in a else len(json.dumps(a))
                add('att:' + at, n)
            elif t == 'system':
                if d.get('subtype') == 'compact_boundary':
                    compactions += 1
                    resident.clear()

    rows = []
    for mid in order:
        r = calls[mid]
        if r is None:
            continue
        src = req_src.get(r[9]) if r[9] else None
        rows.append(r[:9] + (src[0] if src else None, src[1] if src else None, src[2] if src else None))
    out.update(calls=rows, resid=dict(resid), added=dict(added), cnt=dict(cnt), uses=dict(uses),
               shapes=shapes, cost_state=cost_state, compactions=compactions,
               big=sorted(big_results, reverse=True)[:15])
    return out


def main():
    files = glob.glob(os.path.join(ROOT, '**', '*.jsonl'), recursive=True)
    files.sort(key=lambda f: -os.path.getsize(f))
    res = []
    with Pool(max(2, (os.cpu_count() or 4) - 1)) as p:
        for i, r in enumerate(p.imap_unordered(scan, files, chunksize=4)):
            res.append(r)
            if i % 500 == 0:
                print(i, len(files), flush=True)
    json.dump(res, open(sys.argv[1], 'w'))
    print('done', len(res))


if __name__ == '__main__':
    main()
