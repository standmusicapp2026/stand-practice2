# Composer: pasting more music than there are bars left adds the bars
import asyncio, json
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
  await E.createComposition({ title: 'Paste', insts: ['violin', 'piano'], time: [4, 4], bars: 4 });
  await new Promise(r => setTimeout(r, 900));
  const C = window.__compose, T = window.__composeTest, S = C.score, all = M.allStaves(S), info = M.staffInfo(S);
  C.tool.dur = 4; C.tool.dots = 0;
  for (const s of info) for (let m = 0; m < 4; m++) for (let b = 0; b < 4; b++) T.commitWrite({ staff: { st: s.st, inst: s.inst }, meas: { m }, t: b * 480, p: (m + b) % 6 });
  const out = {};
  // one staff: copy 4 bars, paste at bar 3
  T.selectBars(all[0], all[0], 0, 3); T.syncSelBar();
  const btn = (t) => [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find((b) => b.textContent.trim() === t);
  btn('Copy').click();
  T.selectBars(all[0], all[0], 2, 2); T.syncSelBar(); btn('Paste').click(); await new Promise(r => setTimeout(r, 100));
  const notes = (st, m) => st.bars[m].filter((e) => !e.rest).length;
  out.one = { bars: C.score.measures.length, last: M.allStaves(C.score)[0].bars.map((b, m) => notes(M.allStaves(C.score)[0], m)) };
  // all staves: copy bars 0-3, paste at bar 5
  const all2 = M.allStaves(C.score);
  T.selectBars(all2[0], all2[all2.length - 1], 0, 3); T.syncSelBar(); btn('Copy').click();
  T.selectBars(all2[0], all2[0], 5, 5); T.syncSelBar(); btn('Paste').click(); await new Promise(r => setTimeout(r, 100));
  const all3 = M.allStaves(C.score);
  out.lanes = { bars: C.score.measures.length, staves: all3.map((s) => s.bars.map((b, m) => notes(s, m)).join('')) };
  // every bar adds up
  out.sums = all3.every((s) => s.bars.every((b, m) => b.reduce((a, e) => a + M.ticksOf(e, M.timeAt(C.score, m)), 0) === M.barTicks(M.timeAt(C.score, m))));
  out.finalBar = C.score.measures.map((m, i) => m.bar ? i + ':' + m.bar : '').filter(Boolean);
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        print(json.dumps(await pg.evaluate(JS), indent=1)); print(errs); await b.close()
asyncio.run(main())
