# sumbench: one line per set from realbench's JSON results — bars, missed; split into pieces where
# Capture read the bar count right (what Studio's following costs) and where it did not.
#   python3 sumbench.py results1.json [results2.json ...]   (a musicnet file adds the ensemble breakdown)
import json, sys, collections
for f in sys.argv[1:]:
    R = [r for r in json.load(open(f)) if r.get('miss') is not None]
    tb = sum(r['bars'] for r in R); tm = sum(r['miss'] for r in R)
    ok = [r for r in R if not r.get('why')]; bad = [r for r in R if r.get('why')]
    ob = sum(r['bars'] for r in ok); om = sum(r['miss'] for r in ok)
    bb = sum(r['bars'] for r in bad); bm = sum(r['miss'] for r in bad)
    print(f"{f.split('/')[-1]:24s} {len(R):3d} pieces {tb:5d} bars  missed {tm / max(1, tb) * 100:5.1f}%   | count right: {len(ok)} pieces {ob} bars missed {om / max(1, ob) * 100:5.1f}%   | count wrong: {len(bad)} pieces {bb} bars missed {bm / max(1, bb) * 100:5.1f}%")
    if 'musicnet' in f:
        meta = json.load(open('/home/claude/omreval/musicnet/musicnet.json'))
        g = collections.defaultdict(lambda: [0, 0, 0])
        for r in R:
            e = meta.get(r['key'], {}).get('ens', '?'); g[e][0] += 1; g[e][1] += r['bars']; g[e][2] += r['miss']
        for e, (n, b, m) in sorted(g.items(), key=lambda x: -x[1][1]): print(f"    {e:28s} {n:3d} pieces {b:5d} bars  missed {m / max(1, b) * 100:5.1f}%")
