# (whitesq) Zoomed in and out again on a score (pages side by side and scrolled down, vector and
# scanned): the page looks as before, never a white piece over the music.
import asyncio, os, sys, io
from playwright.async_api import async_playwright
from PIL import Image
import numpy as np
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/'
PORT = os.environ.get('PORT', '8765')
FILES = {'vector': '/home/claude/fixtures/vector8.pdf', 'scan': '/home/claude/fixtures/scan10.pdf', 'dragon': '/home/claude/dragon/out/How to Train Your Dragon 2 - Clarinet 1.pdf'}
def blocks(png, box):
    a = np.asarray(Image.open(io.BytesIO(png)).convert('L')).astype(float)
    x0, y0, x1, y1 = [int(v) for v in box]; a = a[max(0, y0):y1, max(0, x0):x1]
    n = 8; h, w = a.shape; out = np.zeros((n, n))
    for i in range(n):
        for j in range(n): out[i, j] = (a[i*h//n:(i+1)*h//n, j*w//n:(j+1)*w//n] < 140).mean()
    return out
async def main():
    fails = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, f in FILES.items():
          for mode in ('pages', 'scroll'):
            ctx = await b.new_context(viewport={'width': 1024, 'height': 1366}, has_touch=True, device_scale_factor=2)
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
            await pg.set_input_files('#importInput', [f])
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
            await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(4000)
            if mode == 'scroll':
                await pg.evaluate("() => window.__scroll.set(true)"); await pg.wait_for_timeout(2500)
            cdp = await ctx.new_cdp_session(pg)
            async def pinch(fct, cx=512, cy=650):
                d0 = 150; await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': cx - d0, 'y': cy, 'id': 1}, {'x': cx + d0, 'y': cy, 'id': 2}]})
                for i in range(1, 11):
                    d = d0 * (1 + (fct - 1) * i / 10)
                    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': cx - d, 'y': cy, 'id': 1}, {'x': cx + d, 'y': cy, 'id': 2}]}); await pg.wait_for_timeout(25)
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            box = await pg.evaluate("() => { const r = [...document.querySelectorAll('#stage .pg')].map((p) => p.getBoundingClientRect()).find((r) => r.top < 650 && r.bottom > 650) || document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left * 2, Math.max(0, r.top) * 2, r.right * 2, Math.min(innerHeight, r.bottom) * 2]; }")
            before = blocks(await pg.screenshot(), box)
            worst = 0; seq = [(2.6, 1600), (0.38, 2500), (3.2, 300), (0.31, 400), (2.0, 2000), (0.5, 3000)]
            for k, (fct, wait) in enumerate(seq):
                await pinch(fct); await pg.wait_for_timeout(wait)
                if fct < 1:
                    shot = await pg.screenshot(); now = blocks(shot, box)
                    # (a piece that had music and now is nearly empty)
                    lost = ((before > 0.02) & (now < before * 0.25)).sum()
                    z = await pg.evaluate("() => { const p = document.querySelector('.zoom-pill'); return p && !p.hidden ? p.textContent : '100%'; }")
                    if lost > worst: worst = lost; open(f'{SP}whitesq-{name}-{mode}.png', 'wb').write(shot)
                    print(f'  {name} {mode} after pinch {k}: zoom {z} empty pieces {lost}', flush=True)
            ok = worst == 0 and not errs
            fails += 0 if ok else 1
            print(('ok   ' if ok else 'FAIL ') + f'{name} {mode}: zoomed in and out, no white piece over the music', errs[:2], flush=True)
            await ctx.close()
        await b.close()
    print('DONE fails', fails)
asyncio.run(main())
