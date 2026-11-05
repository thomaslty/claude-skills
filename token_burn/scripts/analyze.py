"""Print spend split by token type, model, month, agent, repo, effort and context size.

python3 -I analyze.py scan.json [YYYY-MM-DD]   # only calls from that date on
"""
import collections, json, sys, re

R = json.load(open(sys.argv[1]))
SINCE = sys.argv[2] if len(sys.argv) > 2 else None  # 'YYYY-MM-DD' filter on call timestamp

# $ per Mtok: in, out, cache read, cache write 5m, cache write 1h
P = {
    'claude-opus-5-5': (4, 20, .20, 5, 8),
    'claude-opus-5': (5, 25, .5, 6.25, 10),
    'claude-opus-4-8': (5, 25, .5, 6.25, 10),
    'claude-opus-4-7': (5, 25, .5, 6.25, 10),
    'claude-opus-4-6': (5, 25, .5, 6.25, 10),
    'claude-fable-5': (10, 50, 1, 12.5, 20),
    'claude-fable-5-1': (10, 50, .25, 12.5, 20),
    'claude-sonnet-5': (2, 10, .2, 2.5, 4),
    'claude-sonnet-5-5': (2, 10, .2, 2.5, 4),
    'claude-sonnet-4-6': (3, 15, .3, 3.75, 6),
    'claude-haiku-4-5-20251001': (1, 5, .1, 1.25, 2),
    'claude-haiku-5-5': (.1, .5, .01, .125, .2),
}


def price(model):
    return P.get(model) or (0, 0, 0, 0, 0)


def cost(c):
    # c = (model, ts, in, cc5, cc1, cr, out, think, effort, qsrc, qeffort, shape)
    p = price(c[0])
    return dict(inp=c[2] * p[0] / 1e6, out=c[6] * p[1] / 1e6, cr=c[5] * p[2] / 1e6,
                cc5=c[3] * p[3] / 1e6, cc1=c[4] * p[4] / 1e6)


def keep(c):
    if c[0] in (None, '<synthetic>'):
        return False
    if SINCE and (c[1] or '') < SINCE:
        return False
    return True


def repo(project):
    p = project.replace('-Users-thomaslau-', '')
    p = re.sub(r'^(orca-workspaces-|Desktop-toogood-git-ai-|Desktop-toogood-git-|Desktop-personal-|Desktop-|Documents-)', '', p)
    for known in ['Omega-Next-AIO', 'Omega-Sync', 'Omega-SSO', 'Omega-Next', 'claude-skills', 'fundserv-bridge']:
        if p.startswith(known):
            return known
    return p[:40]


tot = collections.Counter()
tok = collections.Counter()
by = collections.defaultdict(collections.Counter)
sess = collections.defaultdict(collections.Counter)
ctx_bucket = collections.defaultdict(collections.Counter)
first_ctx = {'main': [], 'sub': []}
rebuilds = collections.Counter()
calls_n = 0
for r in R:
    rows = [c for c in r['calls'] if keep(c)]
    if not rows:
        continue
    kind = 'sub' if r['sub'] else 'main'
    at = r['agent_type'] or ('?' if r['sub'] else 'main-thread')
    first = rows[0]
    first_ctx[kind].append(first[2] + first[3] + first[4] + first[5])
    for i, c in enumerate(rows):
        calls_n += 1
        k = cost(c)
        d = sum(k.values())
        ctx = c[2] + c[3] + c[4] + c[5]
        for kk, v in k.items():
            tot[kk] += v
        tok['in'] += c[2]; tok['cc5'] += c[3]; tok['cc1'] += c[4]; tok['cr'] += c[5]; tok['out'] += c[6]; tok['think'] += c[7]
        month = (c[1] or '')[:7]
        by['month'][month] += d
        by['month_calls'][month] += 1
        by['model'][c[0]] += d
        by['model_calls'][c[0]] += 1
        by['kind'][kind] += d
        by['agent'][at] += d
        by['agent_calls'][at] += 1
        by['repo'][repo(r['project'])] += d
        by['effort'][str(c[8] or c[10])] += d
        by['effort_out'][str(c[8] or c[10])] += c[6]
        by['qsrc'][str(c[9])] += d
        sess[r['session']]['usd'] += d
        sess[r['session']]['calls'] += 1
        sess[r['session']]['sub_usd'] += d if r['sub'] else 0
        sess[r['session']]['repo_' + repo(r['project'])] = 1
        b = ('<50k' if ctx < 50e3 else '50-100k' if ctx < 100e3 else '100-200k' if ctx < 200e3 else '200-400k' if ctx < 400e3 else '400k-1M')
        ctx_bucket[b]['usd'] += d
        ctx_bucket[b]['calls'] += 1
        ctx_bucket[b]['cr_usd'] += k['cr']
        # a cache rebuild: after the first call, more than half the context is rewritten
        if i > 0 and (c[3] + c[4]) > 0.5 * ctx and ctx > 30000:
            rebuilds['n'] += 1
            rebuilds['usd'] += k['cc5'] + k['cc1']
            rebuilds['tok'] += c[3] + c[4]
        by['ttl'][kind + ':cc5'] += k['cc5']
        by['ttl'][kind + ':cc1'] += k['cc1']

grand = sum(tot.values())
out = {}
out['calls'] = calls_n
out['usd_total'] = grand
out['usd_by_type'] = {k: (round(v), round(100 * v / grand, 1)) for k, v in tot.most_common()}
out['tokens_by_type_M'] = {k: round(v / 1e6, 1) for k, v in tok.items()}
for k in ['month', 'model', 'kind', 'agent', 'repo', 'effort', 'qsrc', 'ttl']:
    out['by_' + k] = [(a, round(v), round(100 * v / grand, 1)) for a, v in by[k].most_common(25)]
out['month_calls'] = dict(sorted(by['month_calls'].items()))
out['agent_calls'] = by['agent_calls'].most_common(25)
out['effort_out_M'] = {k: round(v / 1e6, 1) for k, v in by['effort_out'].items()}
out['ctx_bucket'] = {b: dict(calls=v['calls'], usd=round(v['usd']), pct=round(100 * v['usd'] / grand, 1), cr_usd=round(v['cr_usd']))
                     for b, v in sorted(ctx_bucket.items())}
out['rebuilds'] = dict(n=rebuilds['n'], usd=round(rebuilds['usd']), Mtok=round(rebuilds['tok'] / 1e6, 1))
S = sorted(sess.items(), key=lambda x: -x[1]['usd'])
n = len(S)
usds = [s[1]['usd'] for s in S]
out['sessions'] = n
out['session_share'] = {f'top{p}%': round(100 * sum(usds[:max(1, n * p // 100)]) / grand, 1) for p in (1, 5, 10, 20)}
out['top_sessions'] = [(sid[:8], [k[5:] for k in s if k.startswith('repo_')][0], round(s['usd']), s['calls'], round(100 * s['sub_usd'] / max(s['usd'], 1)))
                       for sid, s in S[:20]]
for k in first_ctx:
    v = sorted(first_ctx[k])
    if v:
        out['first_call_ctx_' + k] = dict(n=len(v), median=v[len(v) // 2], p90=v[int(len(v) * .9)])
json.dump(out, sys.stdout, indent=1, default=str)
