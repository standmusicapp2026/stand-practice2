# Phrasing: a melody in two phrases (a rest between): the last notes of a phrase ease a little, the
# middle is a little louder; 'Exact' stays exact
import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async (style) => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const P = await import('/js/compose/playback.js');
  await E.createComposition({ title: 'Ph', insts: ['violin'], time: [4, 4], bars: 4 });
  await new Promise(r => setTimeout(r, 600));
  const C = window.__compose, T = window.__composeTest, st = M.staffInfo(C.score)[0];
  C.tool.dur = 8;
  const ps = [2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 3, 4, 5, 4, 3];
  for (let i = 0; i < 16; i++) { const m = Math.floor(i / 8) * 2 + 0, t = (i % 8) * 240; T.commitWrite({ staff: { st: st.st, inst: st.inst }, meas: { m: Math.floor(i / 8) * 2 }, t, p: ps[i] }); }
  C.score.sound = { ...(C.score.sound || {}), style };
  const tl = P.buildTimeline(C.score, { humanize: false });
  const ns = tl.notes.filter((n) => n.part === C.score.parts[0].id);
  return ns.map((n, i) => [+(n.t).toFixed(3), +(ns[i + 1] ? ns[i + 1].t - n.t : 0).toFixed(3), +n.vel.toFixed(2)]);
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        for style in ['expressive', 'straight']:
            r = await pg.evaluate(JS, style)
            print(style, 'ioi', [x[1] for x in r]); print('   vel', [x[2] for x in r])
        await b.close()
asyncio.run(main())
