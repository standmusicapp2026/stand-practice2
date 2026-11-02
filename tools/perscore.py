# How the pages sit on the screen is kept with each score: one set sideways stays sideways, the others not
import asyncio, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=60000)
        async def open_(k):
            t = ['Cello Suite No. 1', 'scan10'][k]
            await pg.evaluate("(t) => [...document.querySelectorAll('#grid .card:not(.folder)')].find((c) => c.querySelector('.ttl').textContent === t).click()", t)
            await pg.wait_for_function("document.querySelector('#stage canvas.art')", timeout=20000); await pg.wait_for_timeout(800)
        async def mode(): return await pg.evaluate("() => { document.querySelector('#score [data-panel=settings]')?.click(); const b = document.querySelector('#viewSeg button.on'); const m = b && b.dataset.view; document.querySelector('#panel-settings [data-close]')?.click(); return m + '/' + document.querySelector('#score').dataset.paper; }")
        async def back(): await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(800)
        await open_(0); m0 = await mode()
        await pg.evaluate("() => { document.querySelector('#viewSeg button[data-view=turn]').click(); document.querySelector('#paperSeg button[data-paper=cream]').click(); }"); await pg.wait_for_timeout(500)
        mA = await mode(); await back()
        await open_(1); mB = await mode(); await back()
        await open_(0); mA2 = await mode(); await back()
        async def setv(v): await pg.evaluate("(v) => document.querySelector('#viewSeg button[data-view=' + v + ']').click()", v); await pg.wait_for_timeout(500)
        async def reload_():
            await pg.reload(); await pg.wait_for_timeout(1800)
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=30000)
        seq = []
        for v in ['one', 'auto', 'turn', 'one']:
            await open_(0); await setv(v); await back()
            await open_(1); oB = await mode(); await back()
            await open_(0); a1 = await mode(); await back()
            await reload_(); await open_(0); a2 = await mode(); await back()
            await open_(1); oB2 = await mode(); await back()
            seq.append((v, a1, a2, oB, oB2))
        print('seq', seq)
        okSeq = all(a1.split('/')[0] == v and a2.split('/')[0] == v and oB == m0 and oB2 == m0 for v, a1, a2, oB, oB2 in seq)
        print('PASS' if okSeq else 'FAIL', 'view changes stick, also after a restart')
        names = await pg.evaluate("() => [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map((x) => x.textContent)")
        print('first', m0, 'set', mA, 'other', mB, 'again', mA2, names)
        print('PASS' if mA == 'turn/cream' and mB == m0 and mA2 == 'turn/cream' else 'FAIL', 'per-score view'); print(errs[:3])
        await b.close()
asyncio.run(main())
