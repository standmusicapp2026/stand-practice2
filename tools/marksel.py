import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1180,'height':820}, has_touch=True, device_scale_factor=2); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("""async () => {
          const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          await E.createComposition({ title: 'Marks', insts: ['violin'], time: [4, 4], bars: 4 });
          await new Promise(r => setTimeout(r, 1000));
          const C = window.__compose, T = window.__composeTest; const st = M.staffInfo(C.score)[0];
          const tg = (m, t, p) => ({ staff: { st: st.st, inst: st.inst }, meas: { m }, t, p });
          C.tool.dur = 4; for (let k = 0; k < 4; k++) T.commitWrite(tg(0, k*480, 4));
          const bar = C.score.parts[0].staves[0].bars[0];
          bar[0].art = ['stacc', 'acc']; bar[1].art = ['trill']; bar[2].dyn = 'mf'; bar[3].art = ['ferm'];
          window.__composeRelayout(); document.querySelector('.tour-skip')?.click();
        }""")
        await pg.wait_for_timeout(600)
        await pg.evaluate("() => document.querySelector('.tour-skip')?.click()"); await pg.wait_for_timeout(300)
        # find screen positions of mark boxes
        marks = await pg.evaluate("""() => { const C = window.__compose; const hit = C.hits[0]; const cv = document.querySelectorAll('#cpPages canvas')[0]; const r = cv.getBoundingClientRect(); const k = r.width / C.lay.W;
          return hit.marks.map(m => ({ name: m.name, x: r.left + (m.x0+m.x1)/2*k, y: r.top + (m.y0+m.y1)/2*k })) }""")
        print(marks)
        out = []
        for m in marks:
            await pg.touchscreen.tap(m['x'], m['y']); await pg.wait_for_timeout(400)
            out.append(await pg.evaluate("() => [document.querySelector('#cpSel .what')?.textContent, !document.querySelector('#cpSel').hidden]"))
            if m['name'] == 'trill': await pg.screenshot(path='/home/claude/shots/marksel.png')
        print(out)
        # delete the accent
        acc = [m for m in marks if m['name']=='acc'][0]
        await pg.touchscreen.tap(acc['x'], acc['y']); await pg.wait_for_timeout(300)
        await pg.evaluate("() => [...document.querySelectorAll('#cpSel button')].find(b=>b.textContent.includes('Delete')).click()"); await pg.wait_for_timeout(300)
        print('arts', await pg.evaluate("() => window.__compose.score.parts[0].staves[0].bars[0][0].art"), errs)
        await b.close()
asyncio.run(main())
