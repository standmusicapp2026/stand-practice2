# Scores: no smaller than the screen; zoomed in, the page can be pulled down past its top to write there
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1024, 'height': 1366}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(3000);")
        cdp = await ctx.new_cdp_session(pg)
        top = lambda: J("const s=document.querySelector('#stage').getBoundingClientRect(), r=document.querySelector('#stage .pg').getBoundingClientRect(); return [Math.round(r.top - s.top), Math.round(r.width), (document.querySelector('.zoom-pill').hidden ? '100%' : document.querySelector('.zoom-pill').textContent)]")
        async def pinch(f, cx=512, cy=700):
            d0 = 200; await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': cx - d0, 'y': cy, 'id': 1}, {'x': cx + d0, 'y': cy, 'id': 2}]})
            for i in range(1, 9):
                d = d0 * (1 + (f - 1) * i / 8)
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': cx - d, 'y': cy, 'id': 1}, {'x': cx + d, 'y': cy, 'id': 2}]}); await pg.wait_for_timeout(20)
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(700)
        async def drag(dy, x=512, y=500):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
            for i in range(1, 13):
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y + dy * i / 12}]}); await pg.wait_for_timeout(30)
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(700)
        print('start', await top())
        await pinch(0.6); print('pinch smaller (score)', await top())
        await J("document.querySelector('#inkBtn').click(); await sleep(400);")
        await pinch(2.0); print('pinch bigger', await top())
        await drag(900); print('dragged down a lot', await top(), 'page', await J("return document.querySelector('#pageLabel').textContent"))
        await drag(-2500); print('dragged up a lot', await top())
        await J("document.querySelector('#zoomBtn').click(); await sleep(200);")
        print('presets', await J("return [...document.querySelectorAll('#zoomPresets button')].filter(b=>!b.hidden).map(b=>b.textContent)"))
        await J("for (let i=0;i<8;i++){ document.querySelector('#zoomOut').click(); await sleep(60);} await sleep(400);"); print('zoom out button x8', await top())
        await J("document.querySelector('#zoomBtn').click(); document.querySelector('#inkDone').click(); await sleep(300); document.querySelector('#backBtn').click(); await sleep(800);")
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500);")
        print('notebook open', await J("return !!document.querySelector('#score.nbmode')"))
        await J("document.querySelector('#inkDone')?.click(); await sleep(300);")
        await pinch(0.6); print('pinch smaller (notebook)', await top())
        print('errors', errs[:5]); await b.close()
asyncio.run(main())
