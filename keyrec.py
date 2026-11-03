# Records what the drone's ear hears in each test piece (every 40 ms: the level, the note, the chroma),
# so the deciding can be replayed quickly with other settings (keytune.py). SEEDS=+1000 for other melodies.
import asyncio, json, os
from playwright.async_api import async_playwright
src = open('/home/claude/tools/keybench.py').read().split('async def main')[0]; kb = {}
os.environ.setdefault('SEEDOFF', '0')
exec(src.replace('piece(1', 'piece(int(os.environ["SEEDOFF"]) + 1').replace('piece(2', 'piece(int(os.environ["SEEDOFF"]) + 2').replace('piece(3', 'piece(int(os.environ["SEEDOFF"]) + 3').replace('piece(4', 'piece(int(os.environ["SEEDOFF"]) + 4').replace('chrom_passing(300', 'chrom_passing(int(os.environ["SEEDOFF"]) + 300'), kb)
OUT = os.environ.get('OUT', '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/keyrec.json')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(800)
        await pg.evaluate('() => { globalThis.__kfRange = [36, 84]; }')
        await pg.add_script_tag(content=open('/home/claude/tools/keyreal.js').read())
        out = []
        for name, start, notes, bounds in kb['scen']():
            secs = max(x[1] + x[2] for x in notes) + 1.5
            await pg.evaluate('() => { globalThis.__kfRec = []; }')
            await pg.evaluate("(o) => window.__keyReal(o)", {'notes': notes, 'secs': secs, 'key': start})
            rec = await pg.evaluate('() => globalThis.__kfRec.map((r) => [Math.round(r[0]), +r[1].toFixed(3), +r[2].toPrecision(4), r[3], r[4] ? r[4].map((v) => +v.toPrecision(3)) : null])')
            out.append({'name': name, 'start': start, 'bounds': [(a, min(bb, secs), pc, mi) for a, bb, pc, mi in bounds], 'secs': secs, 'rec': rec})
            print(name, len(rec), flush=True)
        json.dump(out, open(OUT, 'w'))
        await b.close()
asyncio.run(main())
