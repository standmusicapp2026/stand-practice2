# A wink's page turn: from the turn to the new page on screen (CPU slowed 4x like an older iPad)
import asyncio, time, os
from playwright.async_api import async_playwright
F = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        for f in ['vector8.pdf', 'scan10.pdf']:
            await pg.set_input_files('#importInput', [F + f])
            await pg.wait_for_timeout(4000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(3000);")
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        res = []
        for k in range(4):
            await pg.wait_for_timeout(2500)
            r = await J("""const before = document.querySelector('#stage .spread'); const t0 = performance.now(); window.standTurn(1);
              while (document.querySelector('#stage .spread') === before) await new Promise(r => requestAnimationFrame(r));
              const t1 = performance.now(); const sp = document.querySelector('#stage .spread');
              while (sp.classList.contains('fade')) await new Promise(r => requestAnimationFrame(r));
              return [Math.round(t1 - t0), Math.round(performance.now() - t0), document.querySelector('#pageLabel').textContent];""")
            res.append(r); print('turn', k + 1, 'new page in', r[0], 'ms, settled', r[1], 'ms', r[2], flush=True)
        print('errors', errs[:3]); await b.close()
asyncio.run(main())
