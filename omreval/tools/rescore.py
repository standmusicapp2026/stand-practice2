# rescore: results scored again against the set's truth as it is now (after a fix to the truth), from
# the times kept with each piece. python3 rescore.py SET results.json [more.json ...]
import json, sys, importlib.util, os
SET = sys.argv[1]; D = f'/home/claude/omreval/{SET}'
META = json.load(open(f'{D}/{SET}.json'))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'realbench.py')).read()
ns = {}; exec(src[src.index('def score('):src.index('def vid(')], ns); score = ns['score']
tb = tm = 0; n = 0
for f in sys.argv[2:]:
    R = json.load(open(f))
    for r in R:
        if r.get('miss') is None or r['key'] not in META: continue
        got = r['times'][:len(r['segs'])] if r.get('segs') else r['times'][:-1]
        nb, miss, err, rel, why = score(META[r['key']]['T'], got)
        if miss != r['miss']: print(r['key'], r['miss'], '->', miss)
        r.update(bars=nb, miss=miss, err=err, rel=rel, why=why); tb += nb; tm += miss; n += 1
    json.dump(R, open(f, 'w'))
print(f'{n} pieces {tb} bars missed {tm} ({tm / max(1, tb) * 100:.1f}%)')
