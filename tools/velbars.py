# The piano's mean key velocity per bar as the app plays a score (for comparing with a pianist's).
import asyncio, json, os, sys
from playwright.async_api import async_playwright
JS = r"""
async ([xml, prep]) => {
  const X = await import('/js/compose/musicxml.js'); const P = await import('/js/compose/playback.js');
  let sc = X.fromMusicXML(xml); sc = sc.score || sc;
  if (prep) await eval(prep)(sc);
  const tl = P.buildTimeline(sc, { from: 0, humanize: false });
  const pid = sc.parts[1].id; const bars = {};
  for (const n of tl.notes) if (n.part === pid) (bars[n.m + 1] = bars[n.m + 1] || []).push(n.vel * 127);
  const out = {}; for (const [k, v] of Object.entries(bars)) out[k] = v.reduce((a, b) => a + b, 0) / v.length;
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate(JS, [open(sys.argv[1]).read(), open(sys.argv[2]).read() if len(sys.argv) > 2 else None])
        ref = json.load(open('/home/claude/bmeth/work/ref_barvel.json'))
        ks = sorted(set(ref) & set(r), key=int)
        import numpy as np
        a = np.array([ref[k] for k in ks]); c = np.array([r[k] for k in ks])
        print('bar  ref  app'); print(' '.join(f'{k}:{ref[k]:.0f}/{r[k]:.0f}' for k in ks))
        print('corr', round(float(np.corrcoef(a, c)[0, 1]), 3), 'mean |diff|', round(float(np.abs(a - c).mean()), 1), 'mean diff', round(float((c - a).mean()), 1))
        await b.close()
asyncio.run(main())
