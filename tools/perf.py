import asyncio, sys, json, time
from playwright.async_api import async_playwright
FIX = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/fixtures/scan10.pdf'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type in ('error',) and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        cdp = await ctx.new_cdp_session(pg)
        await pg.set_input_files('#importInput', FIX)
        t0 = time.time()
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length > 0", timeout=60000)
        print('import ms', int((time.time()-t0)*1000))
        await pg.wait_for_timeout(4000)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        t0 = time.time()
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=60000)
        print('open ms', int((time.time()-t0)*1000))
        for k in range(4):
            t0 = time.time()
            lab = await pg.evaluate("() => document.querySelector('#pageLabel')?.textContent")
            await pg.keyboard.press('ArrowRight')
            await pg.wait_for_function(f"document.querySelector('#pageLabel')?.textContent !== {json.dumps(lab)} && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=60000)
            print('turn', k, int((time.time()-t0)*1000), await pg.evaluate("() => document.querySelector('#pageLabel')?.textContent"))
            await pg.wait_for_timeout(int(__import__("os").environ.get("GAP","300")))
        print('errors', errs[:6])
        await b.close()
asyncio.run(main())
