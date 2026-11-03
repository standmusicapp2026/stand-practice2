# Replays what the ear heard (keyrec.py) through the deciding, with many settings, quickly.
# Score: share of the time on the right key, minus the waits, minus a heavy cost for each wrong move.
#   REC=<file> (default the scratchpad's keyrec.json), GRID='{"__kfEps":[0.05,0.1],...}', BASE='{...}'
import asyncio, json, os, itertools, sys
from playwright.async_api import async_playwright
src = open('/home/claude/tools/keybench.py').read().split('async def main')[0]; kb = {}; exec(src, kb)
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/'
RECS = [x for x in os.environ.get('REC', SP + 'keyrec.json').split(',')]
REPLAY = r"""
async ([data, g]) => {
  const KF = await import('/js/keyfollow.js');
  for (const k of Object.keys(globalThis)) if (k.startsWith('__kf')) delete globalThis[k];
  Object.assign(globalThis, { __kfRange: [36, 84] }, g);
  const out = [];
  for (const sc of data) {
    let now = 0; const ev = [];
    const kf = new KF.KeyFollower((k) => ev.push([+(now / 1000).toFixed(1), k.pc + (k.minor ? 'm' : '')]), () => {});
    kf.clock = () => now; kf._init(); kf.set(sc.start[0], !!sc.start[1]);
    for (const [t, dt, e, midi, chroma] of sc.rec) { now = t; kf._step(t, dt, e, midi, chroma); }
    out.push(ev);
  }
  return out;
}
"""
def score(data, evs):
    accs, lats, wrong = [], [], 0
    for sc, ev in zip(data, evs):
        a, l, w = kb['judge'](ev, sc['start'], [tuple(b) for b in sc['bounds']], sc['secs'])
        accs.append(a); lats += l; wrong += w
    acc = sum(accs) / len(accs); lat = sum(lats) / max(1, len(lats))
    return acc, lat, wrong, acc * 100 - lat * 0.8 - wrong * 6
async def main():
    datas = [json.load(open(r)) for r in RECS]
    base = json.loads(os.environ.get('BASE', '{}'))
    grid = json.loads(os.environ.get('GRID', '{}'))
    keys = list(grid)
    combos = [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])] or [{}]
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        rows = []
        for c in combos:
            g = {**base, **c}; res = []
            for data in datas:
                evs = await pg.evaluate(REPLAY, [data, g]); res.append(score(data, evs))
            acc = sum(r[0] for r in res) / len(res); lat = sum(r[1] for r in res) / len(res); wr = sum(r[2] for r in res); sc = sum(r[3] for r in res) / len(res)
            rows.append((sc, acc, lat, wr, c)); print(f'{sc:6.1f}  on key {acc*100:5.1f}%  wait {lat:5.1f} s  wrong {wr:2d}  {c}', flush=True)
        rows.sort(key=lambda r: -r[0])
        print('BEST'); [print(f'{r[0]:6.1f}  on key {r[1]*100:5.1f}%  wait {r[2]:5.1f} s  wrong {r[3]:2d}  {r[4]}') for r in rows[:6]]
        if os.environ.get('SHOW'):
            data = datas[0]; evs = await pg.evaluate(REPLAY, [data, {**base, **json.loads(os.environ['SHOW'])}])
            for sc, ev in zip(data, evs):
                a, l, w = kb['judge'](ev, sc['start'], [tuple(b) for b in sc['bounds']], sc['secs']); print(f"  {sc['name']:34s} {a*100:5.1f}% {l} wrong {w} {ev}")
        await b.close()
asyncio.run(main())
