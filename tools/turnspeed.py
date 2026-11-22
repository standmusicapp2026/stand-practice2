# The first time through a score: how long does each page turn take, reading at a normal pace?
# The iPad's slower processor is imitated (CPU slowed 4x via CDP, Chromium). Measured from the turn
# until the new page is on the screen (its page number shown, its picture drawn).
import asyncio, os, sys, time, statistics
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
SLOW = float(os.environ.get('SLOW', '4'))
READ = int(os.environ.get('READ', '1500'))   # ms looking at each page before turning
LIMIT = float(os.environ.get('LIMIT', '0'))  # fail if the median turn is slower than this (ms)
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def run(b, name, vw, vh, fix, turns, half=False):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); [...document.querySelectorAll('.ask-back button')].find((b) => /Not now/.test(b.textContent))?.click();")
    await pg.set_input_files('#importInput', [fix])
    await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
    await pg.wait_for_timeout(1500)
    if BR == 'chromium' and SLOW > 1:
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': SLOW})
    t0 = time.time()
    await J("document.querySelector('#grid .card:not(.folder)').click()")
    await pg.wait_for_function("document.querySelector('#stage .pg canvas.art') && document.querySelector('#stage .pg canvas.art').width > 0", timeout=60000)
    opened = (time.time() - t0) * 1000
    times = []
    for k in range(turns):
        await pg.wait_for_timeout(READ)
        r = await J("""const lab = document.querySelector('#pageLabel'), before = lab.textContent, art0 = document.querySelector('#stage .pg canvas.art');
          const t0 = performance.now(); window.standTurn(1);
          for (let i = 0; i < 600; i++) { await new Promise((r) => requestAnimationFrame(r)); const art = document.querySelector('#stage .pg canvas.art');
            if (lab.textContent !== before && art && art !== art0 && art.width > 0) return [performance.now() - t0, lab.textContent]; }
          return [99999, lab.textContent];""")
        times.append(r[0])
    await ctx.close()
    med = statistics.median(times)
    print(f'   {name}: opened in {opened:.0f} ms; turns (ms): ' + ' '.join(f'{t:.0f}' for t in times) + f'  median {med:.0f}, worst {max(times):.0f}')
    if LIMIT: check(med <= LIMIT and max(times) <= LIMIT * 3, f'{name}: turning through it the first time is quick (median {med:.0f} ms, worst {max(times):.0f} ms; limit {LIMIT:.0f})')
    return times

async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        F = '/home/claude/fixtures/'
        for fix, turns in [(F + 'vector8.pdf', 6), (F + 'imslp12.pdf', 8), (F + 'scan10.pdf', 7), (F + 'real/violin1017.pdf', 7)]:
            for name, vw, vh in [('ipad-land', 1180, 820), ('ipad-portrait', 820, 1180), ('ipad-pro13', 1376, 1032)]:
                await run(b, f'{fix.split("/")[-1]} {name}', vw, vh, fix, turns)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
