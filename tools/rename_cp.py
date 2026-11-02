# A composition renamed in Layout keeps its name, also when Compose is left straight away while typing
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        await pg.evaluate("async () => { const E = await import('/js/compose/editor.js'); await E.createComposition({ insts: ['cello'], time: [4, 4], bars: 3 }); }")
        await pg.wait_for_timeout(1500)
        res = []
        for i, how in enumerate(['close', 'back', 'back']):
            if i: await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
            await pg.evaluate("() => document.querySelector('#cpTitle').click()"); await pg.wait_for_timeout(500)
            print('panel', await pg.evaluate("() => [document.querySelector('#panel-cplayout').hidden, document.querySelector('#compose').hidden]")); await pg.focus('#lyTitle'); await pg.fill('#lyTitle', 'Obra %d' % i)
            if how == 'close': await pg.evaluate("() => document.querySelector('#panel-cplayout [data-close]').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("() => document.querySelector('#cpBack').click()"); await pg.wait_for_timeout(2000)
            l1 = await pg.evaluate("() => document.querySelector('#grid .card:not(.folder) .ttl').textContent")
            await pg.reload(); await pg.wait_for_timeout(2500)
            l2 = await pg.evaluate("() => document.querySelector('#grid .card:not(.folder) .ttl').textContent")
            res.append((how, 'Obra %d' % i, l1, l2))
        print(res)
        print('PASS' if all(t == a == b2 for _, t, a, b2 in res) else 'FAIL', 'composition renamed keeps its name'); print(errs[:3])
        await b.close()
asyncio.run(main())
