# Live line (while the Pencil is down) against the same line after it lifts: same sharpness?
# python3 inkblur.py webkit|chromium [zoom]
import asyncio, sys, io
from playwright.async_api import async_playwright
from PIL import Image
import numpy as np
ENG = sys.argv[1] if len(sys.argv) > 1 else 'webkit'; ZOOM = sys.argv[2] if len(sys.argv) > 2 else '1'
DOWN = '''async ([x, y]) => { const t = document.elementFromPoint(x, y); window.__t = t;
  t.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: 0.5, buttons: 1 })); }'''
MOVE = '''async (pts) => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); const st = document.querySelector('#stage');
  for (const [x, y] of pts) { st.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: 0.5, buttons: 1 })); await sleep(16); } }'''
UP = '''async ([x, y]) => { document.querySelector('#stage').dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: 0, buttons: 0 })); }'''
def sharp(png):
    a = np.asarray(Image.open(io.BytesIO(png)).convert('L')).astype(float)
    dark = (a < 128).sum(); mid = ((a >= 40) & (a <= 215)).sum()
    gy, gx = np.gradient(a); g = np.hypot(gx, gy)
    return {'dark': int(dark), 'mid/dark': round(mid / max(1, dark), 3), 'maxgrad': round(float(np.percentile(g, 99.5)), 1)}
async def main():
    async with async_playwright() as p:
        import tempfile
        ctx = await getattr(p, ENG).launch_persistent_context(tempfile.mkdtemp(), viewport={'width': int(__import__('os').environ.get('VW', '1024')), 'height': int(__import__('os').environ.get('VH', '1366'))}, device_scale_factor=2, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(900)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        if __import__('os').environ.get('NB'):
            await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(3000);")
        else:
            await pg.set_input_files('#importInput', [__import__('os').environ.get('FIX', '/home/claude/fixtures/vector8.pdf')])
            await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=90000)
            await J("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(5000)
            await J("document.querySelector('#inkBtn').click(); await sleep(600);")
        if ZOOM != '1':
            await J(f"document.querySelector('#zoomBtn').click(); await sleep(100); document.querySelector('#zoomPresets [data-z=\"{ZOOM}\"]').click(); await sleep(100); document.querySelector('#zoomBtn').click(); await sleep(3000);")
        # an empty place on the page: between systems near the middle
        x0, y0 = int(__import__('os').environ.get('X0', '300')), int(__import__('os').environ.get('Y0', '640'))
        pts = [[x0 + i * 6, y0 + 30 * np.sin(i / 6)] for i in range(60)]
        clip = {'x': x0 - 20, 'y': y0 - 50, 'width': 400, 'height': 100}
        await pg.evaluate(DOWN, pts[0]); await pg.evaluate(MOVE, pts[1:])
        # keep the Pencil moving a hair while the picture is taken (a still Pencil makes a neat shape)
        await pg.evaluate("([x, y]) => { let k = 0; window.__jig = setInterval(() => { k++; document.querySelector('#stage').dispatchEvent(new PointerEvent('pointermove', { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x + (k % 2) * 5, clientY: y, pressure: 0.5, buttons: 1 })); }, 30); }", pts[-1])
        await pg.wait_for_timeout(200)
        live = await pg.screenshot(clip=clip)
        await pg.evaluate("() => clearInterval(window.__jig)")
        await pg.evaluate(UP, pts[-1]); await pg.wait_for_timeout(1500)
        done = await pg.screenshot(clip=clip)
        open(f'/home/claude/shots/blur_{ENG}_{ZOOM}_live.png', 'wb').write(live); open(f'/home/claude/shots/blur_{ENG}_{ZOOM}_done.png', 'wb').write(done)
        print(ENG, 'zoom', ZOOM, 'live', sharp(live), 'after', sharp(done))
        print('geom', await J("const p=document.querySelector('#stage .pg'); const r=p.getBoundingClientRect(); const k=p.querySelector('canvas.ink'); const rk=k.getBoundingClientRect(); return [p.querySelector('.pgi').style.cssText, r.left, r.top, r.width, rk.left, rk.top, rk.width, k.width, getComputedStyle(document.querySelector('#stage .spread')).transform]"))
        print('errors', errs[:3]); await ctx.close()
asyncio.run(main())
