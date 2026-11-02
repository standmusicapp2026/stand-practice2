# A title or composer changed in a score's settings is kept: in the library, when opened again, after a restart
import asyncio, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await getattr(p, os.environ.get('BR', 'chromium')).launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        async def open_():
            await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()")
            await pg.wait_for_function("document.querySelector('#stage canvas.art')", timeout=20000); await pg.wait_for_timeout(1500)
        async def back(): await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(1200)
        async def lib(): return await pg.evaluate("() => document.querySelector('#grid .card:not(.folder) .ttl').textContent")
        res = []
        for i, how in enumerate(['close', 'back', 'tapstage', 'close']):
            await open_()
            await pg.click('#score [data-panel=settings]'); await pg.wait_for_timeout(500)
            t = 'Name %d' % i
            await pg.click('#metaTitle'); await pg.fill('#metaTitle', t)
            await pg.click('#metaComposer'); await pg.fill('#metaComposer', 'Comp %d' % i)
            if how == 'close': await pg.click('#panel-settings [data-close]'); await pg.wait_for_timeout(400); await back()
            elif how == 'back': await back()
            else: await pg.mouse.click(300, 600); await pg.wait_for_timeout(400); await back()
            l1 = await lib()
            await pg.wait_for_timeout(3000)
            await pg.reload(); await pg.wait_for_timeout(2000)
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=30000)
            l2 = await lib()
            await open_(); hdr = await pg.evaluate("() => document.querySelector('#scoreTitle').textContent"); await back()
            res.append((how, t, l1, l2, hdr))
        print(res)
        # an older copy of the score saved after the change (a cover drawn again, the practice time) keeps the new name
        await open_()
        await pg.click('#score [data-panel=settings]'); await pg.wait_for_timeout(400)
        await pg.evaluate("async () => { const { db } = await import('/js/db.js'); window.__old = (await db.all('scores'))[0]; }")
        await pg.click('#metaTitle'); await pg.fill('#metaTitle', 'Nome novo'); await pg.wait_for_timeout(1200)
        await pg.evaluate("async () => { const { db } = await import('/js/db.js'); await db.put('scores', { ...window.__old }); }")
        await pg.click('#panel-settings [data-close]'); await back()
        await pg.evaluate("async () => { const { db } = await import('/js/db.js'); await db.put('scores', { ...window.__old }); }")
        await pg.wait_for_timeout(500)
        await pg.reload(); await pg.wait_for_timeout(2000)
        stale = await lib(); print('after stale copies', stale)
        res.append(('stale', 'Nome novo', stale, stale, stale))
        ok = all(l1 == t and l2 == t and hdr == t for how, t, l1, l2, hdr in res)
        print('PASS' if ok else 'FAIL', 'renamed score keeps its name'); print(errs[:3])
        await b.close()
asyncio.run(main())
