import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, vp in [('ipad', {'width':1180,'height':820}), ('phone', {'width':390,'height':844})]:
            ctx = await b.new_context(viewport=vp, has_touch=True, device_scale_factor=2); pg = await ctx.new_page()
            await pg.add_init_script('window.__noTour = true;')
            errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
            await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
            r = await pg.evaluate("""async () => {
              const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
              await E.createComposition({ title: 'Test', insts: ['cello'], time: [3, 8], bars: 8 });
              await new Promise(r => setTimeout(r, 1200));
              const C = window.__compose, T = window.__composeTest;
              const info = M.staffInfo(C.score); const cello = info[0];
              const tg = (staff, m, t, p) => ({ staff: { st: staff.st, inst: staff.inst }, meas: { m }, t, p });
              C.tool.dur = 1; C.tool.dots = 0; T.commitWrite(tg(cello, 0, 0, 2));
              const bars = C.score.parts[0].staves[0].bars.slice(0, 4).map(b => b.map(e => (e.rest ? 'r' : '') + e.t + '.'.repeat(e.dots||0) + (e.notes && e.notes[0].tie ? '~' : '')).join(' '));
              const ev = C.score.parts[0].staves[0].bars[0][0]; ev.art = ['stacc', 'mord']; ev.dyn = 'p';
              C.mode = 'select'; C.sel.clear(); C.sel.add(ev.id); window.__composeRelayout();
              return bars;
            }""")
            await pg.wait_for_timeout(500)
            await pg.evaluate("() => { const t = window.__composeTest; t && t.syncSelBar && t.syncSelBar(); }")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'/home/claude/shots/selbar_{name}.png')
            await pg.evaluate("() => [...document.querySelectorAll('#cpSel button')].find(b => b.textContent.includes('More'))?.click()")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'/home/claude/shots/selbar_{name}_more.png')
            labels = await pg.evaluate("() => [...document.querySelectorAll('.cp-sel-more button')].map(b => b.textContent)")
            await pg.evaluate("() => [...document.querySelectorAll('.cp-sel-more button')].find(b => b.textContent.includes('Mordent'))?.click()")
            await pg.wait_for_timeout(300)
            art = await pg.evaluate("() => window.__compose.score.parts[0].staves[0].bars[0][0].art")
            print(name, r, labels, art, errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
