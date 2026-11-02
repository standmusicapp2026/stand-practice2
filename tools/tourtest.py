import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(600)
        # skip home tour
        await pg.evaluate("() => document.querySelector('.tour-skip')?.click()")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf']); await pg.wait_for_timeout(4000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(1800)
        res=[]
        for i in range(9):
            st = await pg.evaluate("() => ({ tour: !!document.querySelector('.tour'), title: document.querySelector('.tour-card h3')?.textContent, chromeOff: document.querySelector('#score').classList.contains('chrome-off'), barVis: getComputedStyle(document.querySelector('#topbar')).opacity })")
            res.append(st)
            await pg.wait_for_timeout(2500)
            await pg.mouse.click(700, 500); await pg.wait_for_timeout(400)
        for r in res: print(r)
        print(errs); await b.close()
asyncio.run(main())
