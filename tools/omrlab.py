"""Runs the music-reader bench: python3 omrlab.py [n] [--detail] [--only font=..,deg=..]
Prints per-case scores and averages by font, size and degradation."""
import asyncio, json, sys, itertools, random
from playwright.async_api import async_playwright

def cases(n):
    r = random.Random(7)
    fonts = ['Bravura', 'Leland', 'Leipzig', 'Petaluma']
    degs = ['clean', 'scan', 'photo', 'rough']
    sps = [11, 14, 18, 24]
    clefs = ['treble', 'treble', 'bass', 'alto']
    times = ['4/4', '3/4', '2/4', '6/8']
    out = []
    for i in range(n):
        out.append(dict(seed=i + 1, font=fonts[i % 4], deg=degs[(i // 4) % 4], sp=sps[(i // 2) % 4], clef=r.choice(clefs), key=r.randint(-4, 4), time=r.choice(times)))
    return out

async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 32
    detail = '--detail' in sys.argv
    only = {}
    if '--only' in sys.argv:
        for kv in sys.argv[sys.argv.index('--only') + 1].split(','):
            k, v = kv.split('='); only[k] = v
    cs = [c for c in cases(n) if all(str(c[k]) == v for k, v in only.items())]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1400, 'height': 1000})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        res = []
        for c in cs:
            q = '&'.join(f'{k}={v}' for k, v in c.items())
            await pg.goto(f'http://localhost:8765/dev/omr-lab.html?{q}')
            try:
                await pg.wait_for_function('() => window.done', timeout=90000)
            except Exception as e:
                print('TIMEOUT', q, errs[-1:] if errs else ''); continue
            r = await pg.evaluate('() => window.result')
            res.append(r)
            ok = lambda a, b: 'ok' if str(a) == str(b) else f'{b}!'
            print(f"{r['seed']:3} {r['font']:8} sp{r['sp']:<3} {r['deg']:6} {r['clef']:6} k{r['key']:+d} {r['time']:4} | all {r['all']:.2f} pitch {r['pitch']:.2f} rhy {r['rhythm']:.2f} bars {r['bars'][1]}/{r['bars'][0]} clef {ok(r['clef'], r['gotClef'])} key {ok(r['key'], r['gotKey'])} time {ok(r['time'], r['gotTime'])} {r['ms']}ms")
            if detail:
                for i, (w, g) in enumerate(itertools.zip_longest(r['want'], r['got'], fillvalue='')):
                    if w != g: print(f'     bar {i+1}\n       want {w}\n       got  {g}')
        if errs: print('ERRORS', errs[:3])
        def avg(rows, key): return sum(x[key] for x in rows) / max(1, len(rows))
        print('\nALL   all %.3f pitch %.3f rhythm %.3f  clef %d/%d key %d/%d time %d/%d bars %d/%d' % (
            avg(res, 'all'), avg(res, 'pitch'), avg(res, 'rhythm'),
            sum(r['clef'] == r['gotClef'] for r in res), len(res), sum(r['key'] == r['gotKey'] for r in res), len(res),
            sum(r['time'] == r['gotTime'] for r in res), len(res), sum(r['bars'][0] == r['bars'][1] for r in res), len(res)))
        for field in ['font', 'deg', 'sp', 'clef']:
            groups = {}
            for r in res: groups.setdefault(r[field], []).append(r)
            print(field.ljust(5), '  '.join(f'{k}: {avg(v, "all"):.2f}' for k, v in groups.items()))
        json.dump(res, open('/home/claude/omrlab/last.json', 'w'))
        await b.close()
asyncio.run(main())
