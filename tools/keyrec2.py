# Records what the drone's ear hears (every 40 ms tick: level, note, chroma) for the key bench pieces
# and more, with the drone following the TRUE key 2.5 s late (as a good follower would), so decision
# methods can be tried offline in node (keyplay.mjs) in seconds.
import asyncio, json, os, random
from playwright.async_api import async_playwright
src = open('/home/claude/tools/keybench.py').read().split('async def main')[0]
exec(src)
def extra():
    S = []
    # a tour of near keys, as a piece moves (15-20 s each)
    parts = [(0, False, 20), (7, False, 16), (4, True, 16), (9, True, 16), (5, False, 16), (0, False, 16)]
    n, b = piece(500, parts); S.append(('tour C G Em Am F C', [0, 0], n, b))
    parts = [(2, False, 18), (9, False, 15), (11, True, 15), (2, False, 15)]
    n, b = piece(501, parts, beat=0.2); S.append(('fast D A Bm D', [2, 0], n, b))
    parts = [(10, False, 30), (5, False, 30)]
    n, b = piece(502, parts, beat=0.75); S.append(('slow Bb F', [10, 0], n, b))
    parts = [(4, False, 25), (8, False, 25)]
    n, b = piece(503, parts); S.append(('E -> Ab (far)', [4, 0], n, b))
    parts = [(6, True, 25), (1, True, 25)]
    n, b = piece(504, parts); S.append(('F#m -> C#m', [6, 1], n, b))
    # G major with short tonicizations of D (C# leading to D at some cadences): must not move
    R = random.Random(505); mel, dur = melody(R, 7, False, 50); out = []
    for i, (m, t, d) in enumerate(mel):
        if d > 1.0 and i % 3 == 0 and i > 2: out.append([m - 1 if m % 12 == 2 else m, t - 0.2, 0.18, 0.7])
        out.append([m, t, d, 0.7])
    S.append(('stay: G with V/V touches', [7, 0], sorted(out, key=lambda x: x[1]), [(0.5, 0.5 + dur, 7, False)]))
    return S
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/__real/prelude.mp3', lambda r: r.fulfill(path='/home/claude/real/casals_prelude1.mp3', content_type='audio/mpeg'))
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        for name, start, notes, bounds in scen() + extra():
            secs = max(x[1] + x[2] for x in notes) + 1.5
            dat = [[a + 2.5, pc, int(mi)] for a, bb, pc, mi in bounds]
            r = await pg.evaluate("(o) => window.__keyReal(o)", {'notes': notes, 'secs': secs, 'key': start, 'sens': 0.6, 'droneAt': dat, 'rec': True})
            out[name] = {'start': start, 'bounds': [[a, min(bb, secs), pc, int(mi)] for a, bb, pc, mi in bounds], 'secs': secs, 'notes': notes, 'rec': r['rec']}
            print(name, len(r['rec']), flush=True)
        # the Casals Prelude (G major; the middle goes to D and elsewhere briefly)
        r = await pg.evaluate("(o) => window.__keyReal(o)", {'url': '/__real/prelude.mp3', 'secs': 150, 'key': [7, 0], 'sens': 0.6, 'droneAt': [], 'rec': True})
        out['casals prelude (G/D only)'] = {'start': [7, 0], 'bounds': None, 'allowed': ['7', '2'], 'secs': 150, 'rec': r['rec']}
        print('casals', len(r['rec']), errs[:3])
        await b.close()
    json.dump(out, open('/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/keyrec.json', 'w'))
asyncio.run(main())
