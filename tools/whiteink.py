# (whiteink) A part of a page (half a page, a square), written on, zoomed in, written on again, zoomed
# out: at no moment is a white piece over the music (seen every tenth of a second, against the page
# as it settles).
import asyncio, os, io, sys
from playwright.async_api import async_playwright
from PIL import Image
import numpy as np
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/'
SRC = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/real/user-solo-c.png'
def grid(png, box, n=10):
    a = np.asarray(Image.open(io.BytesIO(png)).convert('L')).astype(float)
    x0, y0, x1, y1 = [int(v) for v in box]; a = a[y0:y1, x0:x1]; h, w = a.shape
    return np.array([[(a[i*h//n:(i+1)*h//n, j*w//n:(j+1)*w//n] < 140).mean() for j in range(n)] for i in range(n)])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, device_scale_factor=2, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', [SRC])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("async () => { document.querySelector('#grid .card:not(.folder)').click(); await new Promise(r => setTimeout(r, 3000)); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const st = document.querySelector('#stage'); const ev = (type, o) => (type === 'pointerdown' ? st : window).dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: o.id, pointerType: o.t, clientX: o.x, clientY: o.y, width: o.w || 1, height: o.w || 1, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 })); " + js + " }")
        pen = lambda x, y, n: J(f"ev('pointerdown', {{ id: {n}, t: 'pen', x: {x}, y: {y} }}); for (let i = 0; i <= 20; i++) {{ ev('pointermove', {{ id: {n}, t: 'pen', x: {x} + i * 4, y: {y} + (i % 5) * 3 }}); await sleep(10); }} ev('pointerup', {{ id: {n}, t: 'pen', x: {x} + 80, y: {y} }}); await sleep(300);")
        def pinch(f, cx=590, cy=410):
            return J(f"const d0 = 60; ev('pointerdown', {{ id: 11, t: 'touch', x: {cx} - d0, y: {cy}, w: 60 }}); ev('pointerdown', {{ id: 12, t: 'touch', x: {cx} + d0, y: {cy}, w: 60 }}); for (let i = 1; i <= 15; i++) {{ const d = d0 * (1 + ({f} - 1) * i / 15); ev('pointermove', {{ id: 11, t: 'touch', x: {cx} - d, y: {cy}, w: 60 }}); ev('pointermove', {{ id: 12, t: 'touch', x: {cx} + d, y: {cy}, w: 60 }}); await sleep(16); }} const d = d0 * {f}; ev('pointerup', {{ id: 11, t: 'touch', x: {cx} - d, y: {cy}, w: 60 }}); ev('pointerup', {{ id: 12, t: 'touch', x: {cx} + d, y: {cy}, w: 60 }});")
        box = await pg.evaluate("() => { const r = document.querySelector('#stage .pg').getBoundingClientRect(); return [Math.max(0, r.left) * 2, Math.max(0, r.top) * 2, Math.min(innerWidth, r.right) * 2, Math.min(innerHeight, r.bottom) * 2]; }")
        worst = 0
        async def watch(tag, secs=2.5):
            nonlocal worst
            shots = []
            for _ in range(int(secs * 8)):
                shots.append(await pg.screenshot()); await pg.wait_for_timeout(40)
            await pg.wait_for_timeout(1500); final = grid(await pg.screenshot(), box)
            for k, s in enumerate(shots):
                g = grid(s, box); lost = int(((final > 0.03) & (g < final * 0.2)).sum())
                if lost > worst: worst = lost; open(f'{SP}whiteink-{tag}-{k}.png', 'wb').write(s)
                if lost: print(f'  {tag} shot {k}: {lost} pieces gone white', flush=True)
        await J("ev('pointerdown', { id: 3, t: 'pen', x: 300, y: 400 }); ev('pointerup', { id: 3, t: 'pen', x: 300, y: 400 }); await sleep(800);")
        await pen(400, 380, 4); await pen(700, 450, 5)
        for rnd in range(3):
            await pinch(2.6); await watch(f'in{rnd}')
            await pen(560, 400, 20 + rnd); await pen(640, 430, 30 + rnd)
            await pinch(0.35); await watch(f'out{rnd}')
        print(('ok   ' if worst == 0 and not errs else 'FAIL ') + 'part of a page, written on and zoomed in and out: never a white piece over the music', worst, errs[:2])
        await b.close()
asyncio.run(main())
