import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024}, device_scale_factor=2); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true; try{localStorage.setItem("standTourDone","1")}catch{}')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("""async () => {
          const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          await E.createComposition({ title: 'Slurs', insts: ['violin'], time: [4, 4], bars: 8 });
          await new Promise(r => setTimeout(r, 1000));
          const C = window.__compose, T = window.__composeTest; const st = M.staffInfo(C.score)[0];
          const tg = (m, t, p) => ({ staff: { st: st.st, inst: st.inst }, meas: { m }, t, p });
          const ps = [2,4,6,7,5,3,1,0, 4,5,6,7,8,9,10,11, 7,5,3,1];
          C.tool.dur = 8; let i = 0; for (let m = 0; m < 2; m++) for (let k = 0; k < 8; k++) T.commitWrite(tg(m, k*240, ps[i++ % ps.length]));
          C.tool.dur = 4; for (let k = 0; k < 4; k++) T.commitWrite(tg(2, k*480, [3,5,7,2][k]));
          C.tool.dur = 2; T.commitWrite(tg(3, 0, 4)); T.commitWrite(tg(3, 960, 8));
          const sp = C.score.spans = C.score.spans || [];
          sp.push({ id: 's1', kind: 'slur', st: st.st.id, a: { m: 0, pos: 0 }, b: { m: 0, pos: 720 } });
          sp.push({ id: 's2', kind: 'slur', st: st.st.id, a: { m: 0, pos: 960 }, b: { m: 1, pos: 1680 } });
          sp.push({ id: 's3', kind: 'slur', st: st.st.id, a: { m: 2, pos: 0 }, b: { m: 2, pos: 480 } });
          sp.push({ id: 's4', kind: 'slur', st: st.st.id, a: { m: 2, pos: 960 }, b: { m: 3, pos: 960 } });
          window.__composeRelayout();
          document.querySelector('.tour-skip')?.click();
        }""")
        await pg.wait_for_timeout(800)
        await pg.evaluate("() => document.querySelector('.tour-skip')?.click()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/slurs.png', clip={'x':560,'y':180,'width':800,'height':200})
        await b.close()
asyncio.run(main())
