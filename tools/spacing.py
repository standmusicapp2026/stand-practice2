# Compose: the distances between staves and between lines of music are the same everywhere
import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async (opts) => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const G = await import('/js/compose/engrave.js');
  await E.createComposition({ title: 'Spacing', insts: opts.insts, time: [4, 4], bars: 40 });
  await new Promise(r => setTimeout(r, 800));
  const C = window.__compose, T = window.__composeTest, info = M.staffInfo(C.score);
  C.tool.dur = 4;
  // notes everywhere, and now and then very high or very low ones (ledger lines)
  for (let m = 0; m < 40; m++) for (const s of info) for (let t = 0; t < 4; t++) { const p = (m * 7 + t * 3) % 11 === 0 ? 20 : (m * 5 + t) % 13 === 0 ? -9 : 2 + ((m + t) % 6); T.commitWrite({ staff: { st: s.st, inst: s.inst }, meas: { m }, t: t * 480, p }); }
  Object.assign(C.score.layout, opts.layout || {});
  const lay = G.layoutScore(C.score, {});
  const out = { pages: lay.pages.length, within: [], between: [] };
  for (const pg of lay.pages) {
    pg.systems.forEach((sy, i) => {
      out.within.push(sy.staves.slice(1).map((st, k) => +(st.y - sy.staves[k].y).toFixed(2)).join(','));
      if (i) { const prev = pg.systems[i - 1]; out.between.push(+(sy.top - (prev.top + prev.height)).toFixed(2)); }
    });
  }
  out.within = [...new Set(out.within)]; out.betweenSet = [...new Set(out.between.map((x) => x.toFixed(1)))];
  delete out.between;
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        for o in [{'insts': ['cello']}, {'insts': ['violin', 'cello', 'piano']}, {'insts': ['violin', 'cello', 'piano'], 'layout': {'staffGap': 9, 'sysGap': 14}}]:
            print(json.dumps(o), json.dumps(await pg.evaluate(JS, o)))
        await pg.evaluate("() => window.__composeRelayout()"); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/spacing.png')
        print(errs[:3]); await b.close()
asyncio.run(main())
