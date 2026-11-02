# A composition's cover in the library shows what was last written (it kept the first picture)
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); " + js + " }")
        cover = "const c = [...document.querySelectorAll('#grid .card[data-sid]')].find(x => x.textContent.includes('Cover test')); const bg = c && c.querySelector('.thumb').style.backgroundImage; const u = bg && bg.slice(5, -2); if (!u) return null; const bl = await (await fetch(u)).blob(); return [u.slice(-12), bl.size];"
        await J("await E.createComposition({ title: 'Cover test', insts: ['violin'], time: [4, 4], bars: 4 }); await sleep(800); const C = window.__compose, T = window.__composeTest, st = M.staffInfo(C.score)[0]; C.tool.dur = 4; T.commitWrite({ staff: { st: st.st, inst: st.inst }, meas: { m: 0 }, t: 0, p: 4 }); await sleep(300); document.querySelector('#cpBack, #composeBack, [data-act=compose-back]').click(); await sleep(1500);")
        a = await J(cover); print('cover after first close', a)
        await J("const c = [...document.querySelectorAll('#grid .card[data-sid]')].find(x => x.textContent.includes('Cover test')); c.click(); await sleep(1500); const C = window.__compose, T = window.__composeTest, st = M.staffInfo(C.score)[0]; C.tool.dur = 8; for (let m = 0; m < 4; m++) for (let t = 0; t < 8; t++) T.commitWrite({ staff: { st: st.st, inst: st.inst }, meas: { m }, t: t * 240, p: t }); await sleep(300); document.querySelector('#cpBack, #composeBack, [data-act=compose-back]').click(); await sleep(1500);")
        b2 = await J(cover); print('cover after editing', b2, 'CHANGED' if a and b2 and a != b2 else 'SAME (wrong)')
        print(errs[:3]); await b.close()
asyncio.run(main())
