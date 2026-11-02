# Compose: how long one relayout takes (layout and drawing), at several zooms and score sizes
import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async ([insts, bars]) => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const G = await import('/js/compose/engrave.js');
  await E.createComposition({ title: 'Perf', insts, time: [4, 4], bars });
  await new Promise(r => setTimeout(r, 800));
  const C = window.__compose, T = window.__composeTest;
  C.tool.dur = 8;
  for (const s of M.staffInfo(C.score)) for (let m = 0; m < bars; m++) for (let t = 0; t < 8; t++) T.commitWrite({ staff: { st: s.st, inst: s.inst }, meas: { m }, t: t * 240, p: (m + t) % 9 });
  const out = {};
  for (const z of [1, 2, 3]) {
    C.zoom = z; window.__composeRelayout(); await new Promise(r => setTimeout(r, 300));
    let t0 = performance.now(); for (let i = 0; i < 3; i++) G.layoutScore(C.score); const lay = (performance.now() - t0) / 3;
    t0 = performance.now(); for (let i = 0; i < 3; i++) window.__composeRelayout(); const rel = (performance.now() - t0) / 3;
    out['zoom' + z] = { layout: Math.round(lay), relayout: Math.round(rel) };
  }
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1180,'height':820}, device_scale_factor=2)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        for insts, bars in [(['cello', 'piano'], 16), (['violin', 'viola', 'cello', 'piano'], 64)]:
            print(insts, bars, json.dumps(await pg.evaluate(JS, [insts, bars])))
        await b.close()
asyncio.run(main())
