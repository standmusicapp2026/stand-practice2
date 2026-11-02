# Finger turning with real touch events: swipe, tap at the edges, half-page turns, perform mode
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1024, 'height': 1366}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click()")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=30000)
        await pg.wait_for_timeout(2500)
        cdp = await ctx.new_cdp_session(pg)
        lab = lambda: J("return document.querySelector('#pageLabel').textContent")
        async def swipe(x0, x1, y=700, steps=8, dur=0.15):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y}]})
            for i in range(1, steps + 1):
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * i / steps, 'y': y}]})
                await pg.wait_for_timeout(int(dur * 1000 / steps))
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            await pg.wait_for_timeout(900)
        async def tap(x, y):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            await pg.wait_for_timeout(60)
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            await pg.wait_for_timeout(900)
        print('start', await lab())
        await swipe(800, 200); print('swipe left ->', await lab())
        await swipe(200, 800); print('swipe right ->', await lab())
        await tap(990, 700); print('tap right edge ->', await lab())
        await tap(30, 700); print('tap left edge ->', await lab())
        await tap(512, 700); print('tap middle ->', await lab(), 'chrome', await J("return document.querySelector('#score').className"))
        # slow drag (reading, not turning) should not turn
        await swipe(700, 550, steps=10, dur=0.9); print('slow small drag ->', await lab())
        # half-page turns
        await J("S_half = document.querySelector('#halfTurn'); S_half.checked = true; S_half.dispatchEvent(new Event('change'));")
        for i in range(3):
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(1200); print('half turn', i, await lab(), await J("return !!document.querySelector('.half-line')"))
        await pg.keyboard.press('ArrowLeft'); await pg.wait_for_timeout(1200); print('half back', await lab())
        await J("S_half = document.querySelector('#halfTurn'); S_half.checked = false; S_half.dispatchEvent(new Event('change'));")
        await pg.screenshot(path='/home/claude/shots/touchturn.png')
        print('errors', errs[:5]); await b.close()
asyncio.run(main())
