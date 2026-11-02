# Coming from the build where the first view seen became everyone's: a score never set opens the standard way
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
        await pg.wait_for_timeout(1500)
        # as the earlier build left it: sideways taken as Stand's own, one score set to one page
        await pg.evaluate("""async () => { const { getSetting, setSetting, db } = await import('/js/db.js');
          const s = await getSetting('settings', {}); delete s.viewFix; delete s.scoreViews;
          s.defView = { twoUp: false, onePage: false, turnScore: true, halfTurn: false, paper: 'white', landscapeLock: false }; s.turnScore = true; s.twoUp = false;
          await setSetting('settings', s);
          const all = await db.all('scores'); const a = all.find((x) => x.title === 'scan10'); a.view = { twoUp: false, onePage: true, turnScore: false, halfTurn: false, paper: 'white', landscapeLock: false }; await db.put('scores', a);
          for (const x of all) if (x !== a) { delete x.view; await db.put('scores', x); } }""")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=30000)
        async def open_(t):
            await pg.evaluate("(t) => [...document.querySelectorAll('#grid .card:not(.folder)')].find((c) => c.querySelector('.ttl').textContent === t).click()", t)
            await pg.wait_for_function("document.querySelector('#stage canvas.art')", timeout=20000); await pg.wait_for_timeout(800)
        async def mode(): return await pg.evaluate("() => { document.querySelector('#score [data-panel=settings]')?.click(); const b = document.querySelector('#viewSeg button.on'); const m = b && b.dataset.view; document.querySelector('#panel-settings [data-close]')?.click(); return m; }")
        async def back(): await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(800)
        await open_('Cello Suite No. 1'); u = await mode(); await back()
        await open_('scan10'); s1 = await mode(); await back()
        print('unset', u, 'set', s1)
        print('PASS' if u == 'auto' and s1 == 'one' else 'FAIL', 'unset scores open the standard way, set ones keep theirs'); print(errs[:3])
        await b.close()
asyncio.run(main())
