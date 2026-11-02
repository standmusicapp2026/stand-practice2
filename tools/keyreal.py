# The drone's "It listens" on real cello sound: a Casals recording and practice material played with
# the app's cello samples. It should move only when the key really changes.
import asyncio, json, os, sys, random
from playwright.async_api import async_playwright
def seq(pitches, beat=0.35, start=0.3, lv=0.7):
    out, t = [], start
    for p in pitches:
        if isinstance(p, tuple): m, d = p
        else: m, d = p, 1
        if m is not None: out.append([m, t, beat * d * 0.97, lv])
        t += beat * d
    return out
MAJ = [0, 2, 4, 5, 7, 9, 11, 12]
def scale(root, octs=2, sc=MAJ):
    up = [root + 12 * o + s for o in range(octs) for s in sc[:-1]] + [root + 12 * octs]
    return up + up[-2::-1]
def arp(root, octs=2):
    up = [root + 12 * o + s for o in range(octs) for s in (0, 4, 7)] + [root + 12 * octs]
    return up + up[-2::-1]
R = random.Random(3)
SCEN = {
  # (key, material, allowed changes)
  'G scales and arpeggios': ([7, 0], seq((scale(43) + arp(43)) * 3, 0.3), 0),
  'C chromatic scale': ([0, 0], seq(([36 + i for i in range(25)] + [60 - i for i in range(25)]) * 2, 0.25), 0),
  'open strings, tuning': ([0, 0], seq([(36, 6), (43, 6), (50, 6), (57, 6), (36, 3), (43, 3), (43, 3), (50, 3), (50, 3), (57, 3)] * 2, 0.5), 0),
  'shifting 1-2 half steps (C)': ([0, 0], seq([b + x for b in (36, 43, 50, 57) for x in (2, 3, 2, 3, 4, 5, 4, 5, 2, 3, 4, 5)] * 3, 0.28), 0),
  'D minor melody (raised 6th, 7th)': ([2, 1], seq([R.choice([50, 52, 53, 55, 57, 58, 59, 60, 61, 62, 64, 65]) if i % 8 else 50 for i in range(160)], 0.32), 0),
  'G major then D major (one change)': ([7, 0], seq(scale(43) * 2 + [55, 57, 59, 61, 62, 64, 66, 67, 69, 66, 62, 61, 57, 54, 50, 49, 50] * 4 + scale(50) * 2, 0.3), 1),
}
async def main():
    sens = float(os.environ.get('SENS', '0.6'))
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/__real/prelude.mp3', lambda r: r.fulfill(path='/home/claude/real/casals_prelude1.mp3', content_type='audio/mpeg'))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        total_bad = 0; total_secs = 0
        r = await pg.evaluate("(o) => window.__keyReal(o)", {'url': '/__real/prelude.mp3', 'secs': 150, 'key': [7, 0], 'sens': sens})
        n = len(r['events']); bad = sum(1 for e in r['events'] if e[1] not in ('7', '2')); total_bad += bad; total_secs += 150
        print(f"{'Casals, Bach prelude in G (G, D, G)':40s} changes {n:2d} {r['events']}", flush=True)
        for sn in r.get('snaps') or []: print('   ', sn)
        only = os.environ.get('ONLY')
        for name, (key, notes, allowed) in SCEN.items():
            if only and only not in name: continue
            secs = max(x[1] + x[2] for x in notes) + 1.5
            r = await pg.evaluate("(o) => window.__keyReal(o)", {'notes': notes, 'secs': secs, 'key': key, 'sens': sens})
            n = len(r['events']); bad = abs(n - allowed); total_bad += bad; total_secs += secs
            print(f"{name:40s} changes {n:2d} (should be {allowed}) {r['events']}", flush=True)
        print(f'wrong changes {total_bad} in {total_secs/60:.1f} min'); print(errs[:3])
        print('PASS' if total_bad == 0 else 'FAIL', 'drone follows only real changes of key')
        await b.close()
asyncio.run(main())
