import asyncio, os
from playwright.async_api import async_playwright
OUT = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/cs/pal'
async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820}, device_scale_factor=2)).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.evaluate("async () => { const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'Pal', insts: ['violin'], time: [4, 4], bars: 8 }); }")
        await pg.wait_for_timeout(1500)
        for tab in ['notes', 'dyn', 'text', 'clef', 'bars']:
            await pg.evaluate("(t) => { const C = window.__compose; C.tab = t; window.__composeTest.renderTab(); const p = document.querySelector('#cpPal'); if (p) p.hidden = false; }", tab)
            await pg.wait_for_timeout(300)
            el = await pg.query_selector('#cpPal')
            if el: await el.screenshot(path=f'{OUT}/{tab}.png')
        print(errs[:3]); await b.close()
asyncio.run(main())
