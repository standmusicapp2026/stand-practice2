# A set going from one score to the next: how long until the next score's page is on screen
import asyncio, time, os
from playwright.async_api import async_playwright
F = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', [F + 'imslp12.pdf', F + 'scan10.pdf', F + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=90000)
        await pg.wait_for_timeout(5000)
        ids = await J("const { db } = await import('/js/db.js'); return (await db.all('scores')).map(s => s.id)")
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        items = [{'sid': ids[0], 'a': 1, 'b': 2}, {'sid': ids[1], 'a': 5, 'b': 6}, {'sid': ids[2], 'a': 3, 'b': 4}, {'sid': ids[0], 'a': 7, 'b': 8}]
        await J(f"window.__run.startRun('set', 'Test', {__import__('json').dumps(items)}); await sleep(200);")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=60000)
        for k in range(1, 4):
            await pg.wait_for_timeout(int(os.environ.get('READ', '6000')))   # playing the part
            want = items[k]
            t0 = time.time()
            await J(f"window.__run.runGo({k});")
            await pg.wait_for_function(f"window.__run.RUN.idx === {k} && !window.__run.RUN.busy && document.querySelector('#pageLabel').textContent.startsWith('{want['a']}') && document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=60000)
            print('to part', k + 1, int((time.time() - t0) * 1000), 'ms', await J("return document.querySelector('#pageLabel').textContent"))
        print(errs[:3]); await b.close()
asyncio.run(main())
