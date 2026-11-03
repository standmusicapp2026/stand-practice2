# How well the drone's ear hears the notes themselves: each note it counts, against the note sounding
# then (cello samples, a room, the drone sounding too). Wrong pitch classes push the key the wrong way.
import asyncio, os, random, sys
sys.argv = sys.argv[:1]
from playwright.async_api import async_playwright
import importlib.util
spec = importlib.util.spec_from_file_location('kb', '/home/claude/tools/keybench.py'); kb = importlib.util.module_from_spec(spec)
src = open('/home/claude/tools/keybench.py').read().split('async def main')[0]; exec(src, kb.__dict__)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        await pg.evaluate('() => { globalThis.__noteLog = true; }')
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        tot = good = octv = fifth = other = missed = 0
        for seed, (pc, mi), dr in [(1, (7, False), True), (2, (2, True), True), (3, (3, False), False), (4, (9, False), True)]:
            notes, bounds = kb.piece(seed, [(pc, mi, 30)])
            secs = max(x[1] + x[2] for x in notes) + 1
            r = await pg.evaluate("(o) => window.__keyReal(o)", {'notes': notes, 'secs': secs, 'key': [pc, int(mi)], 'drone': dr})
            heard = r['heard']
            for t, m in heard:
                cur = [n for n in notes if n[1] - 0.02 <= t <= n[1] + n[2] + 0.15]
                if not cur: other += 1; tot += 1; continue
                truth = cur[-1][0]; tot += 1
                d = (m - truth) % 12
                if d and os.environ.get('SHOW'):
                    prev = [n for n in notes if n[1] < cur[-1][1]]
                    print('   at', t, 'heard', m, 'playing', truth, 'since', round(t - cur[-1][1], 2), 'before', prev[-1][0] if prev else None, 'len', round(cur[-1][2], 2))
                if d == 0: good += 1
                elif d in (7, 5): fifth += 1
                else: other += 1
            missed += max(0, len(notes) - len(heard))
            print(f'{kb.NAMES[pc]}{"m" if mi else ""} drone={dr}: notes played {len(notes)}, counted {len(heard)}', flush=True)
        print(f'NOTES right pitch class {good}/{tot} ({100*good/max(1,tot):.1f}%), a fifth/fourth off {fifth}, other wrong {other}, not counted ~{missed}')
        await b.close()
asyncio.run(main())
