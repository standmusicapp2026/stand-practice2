import asyncio, sys, json, time
from playwright.async_api import async_playwright
FIX = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True)
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        logs=[]
        pg.on('console', lambda m: logs.append(m.text) if m.text.startswith('RQ') else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        cdp = await ctx.new_cdp_session(pg)
        await pg.set_input_files('#importInput', FIX)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length > 0", timeout=60000)
        await pg.wait_for_timeout(3000)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        t00=time.time()
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()")
        await pg.wait_for_timeout(6000)
        t0=time.time(); await pg.keyboard.press('ArrowRight')
        await pg.wait_for_function("[...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10) && document.querySelector('#pageLabel').textContent.startsWith('3')")
        print('turn', int((time.time()-t0)*1000), 'at', int((t0-t00)*1000))
        await pg.wait_for_timeout(2000)
        for l in logs: print(l)
        await b.close()
asyncio.run(main())
