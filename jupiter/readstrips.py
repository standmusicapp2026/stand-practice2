# Read staff strips with Stand's Capture (recogniseBest) and print each bar as note names.
# python3 readstrips.py dir name1,name2,...  -> also writes dir/read.json
import asyncio, base64, json, sys, os
from playwright.async_api import async_playwright
D, names = sys.argv[1], sys.argv[2].split(',')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        out = {}
        for nm in names:
            src = 'data:image/png;base64,' + base64.b64encode(open(f'{D}/{nm}.png', 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js'); const M = await import('/js/compose/model.js');
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const r = await O.recogniseBest(c, {}); if (!r) return null;
              let clef = r.clef || 'treble', key = r.key || 0; const bars = [];
              const NM = ['C','D','E','F','G','A','B'];
              r.bars.forEach((bar, i) => {
                const ch = r.changes[i] || {}; if (ch.clef) clef = ch.clef; if (ch.key !== undefined) key = ch.key;
                const evs = [];
                for (const it of bar) {
                  const d = (it.t + '.'.repeat(it.dots || 0)) + (it.tup ? 't' : '');
                  if (it.rest) { evs.push('r' + d); continue; }
                  const cl = M.CLEFS[it.clef || clef] || M.CLEFS[clef];
                  const ns = it.ps.map((p) => { const s = cl.bottom + p; const a = it.acc && it.acc[p] !== undefined ? it.acc[p] : M.keyAlter(key, s);
                    return NM[((s % 7) + 7) % 7] + (a > 0 ? '#'.repeat(a) : a < 0 ? 'b'.repeat(-a) : '') + (Math.floor(s / 7)); });
                  evs.push(ns.join('+') + ':' + d + (it.tie ? '~' : ''));
                }
                bars.push(evs.join(' '));
              });
              return { clef: r.clef, key: r.key, time: r.time, bars };
            }""", src)
            out[nm] = r
            print(f"--- {nm}  clef {r and r['clef']} key {r and r['key']} time {r and r['time']}")
            if r:
                for i, bar in enumerate(r['bars']): print(f'  {i+1:2d} | {bar}')
        json.dump(out, open(f'{D}/read.json', 'w'), indent=1)
        await b.close()
asyncio.run(main())
