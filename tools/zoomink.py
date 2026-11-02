# Markings open: two 60 px fingers pinch-zoom; a pen stroke stays where it was written on the music,
# and is drawn at the screen's sharpness once zoomed
import asyncio, os
from playwright.async_api import async_playwright
S = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, device_scale_factor=2)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("async () => { document.querySelector('#grid .card:not(.folder)').click(); await new Promise(r => setTimeout(r, 2500)); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const st = document.querySelector('#stage'); const ev = (type, o) => (type === 'pointerdown' ? st : window).dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: o.id, pointerType: o.t, clientX: o.x, clientY: o.y, width: o.w || 1, height: o.w || 1, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 })); " + js + " }")
        # open the markings with the pen, then write a red-ish stroke (a cross) at a known place
        await J("ev('pointerdown', { id: 3, t: 'pen', x: 300, y: 400 }); ev('pointerup', { id: 3, t: 'pen', x: 300, y: 400 }); await sleep(800);")
        await J("ev('pointerdown', { id: 4, t: 'pen', x: 250, y: 380 }); for (let i = 0; i <= 20; i++) { ev('pointermove', { id: 4, t: 'pen', x: 250 + i * 5, y: 380 + i * 3 }); await sleep(10); } ev('pointerup', { id: 4, t: 'pen', x: 350, y: 440 }); await sleep(900);")
        await pg.screenshot(path=S + 'zi0.png')
        z0 = await J("return (document.querySelector('.zoom-pill, #zoomReset, .zoompill') || {}).textContent || getComputedStyle(document.querySelector('#stage .spread')).transform")
        # pinch with two ordinary fingers, 0.8 s after writing
        await J("await sleep(800); ev('pointerdown', { id: 11, t: 'touch', x: 400, y: 400, w: 60 }); ev('pointerdown', { id: 12, t: 'touch', x: 500, y: 400, w: 60 }); for (let i = 1; i <= 15; i++) { ev('pointermove', { id: 11, t: 'touch', x: 400 - i * 8, y: 400, w: 60 }); ev('pointermove', { id: 12, t: 'touch', x: 500 + i * 8, y: 400, w: 60 }); await sleep(16); } ev('pointerup', { id: 11, t: 'touch', x: 280, y: 400, w: 60 }); ev('pointerup', { id: 12, t: 'touch', x: 620, y: 400, w: 60 }); await sleep(6000);")
        z1 = await J("return (document.querySelector('.zoom-pill, #zoomReset, .zoompill') || {}).textContent || getComputedStyle(document.querySelector('#stage .spread')).transform")
        print(await J("return [...document.querySelectorAll('#stage .pgi')].map(p => [...p.querySelectorAll('canvas')].map(c => [c.className, c.width, c.height, Math.round(c.getBoundingClientRect().width), c.style.cssText.slice(0, 60)]))"))
        info = await J("""const p = document.querySelector('#stage .pgi'); const ink = p.querySelector('canvas.ink'), art = p.querySelector('canvas.art');
          const ri = ink.getBoundingClientRect(), ra = art.getBoundingClientRect();
          return { inkPx: [ink.width, ink.height], inkCss: [Math.round(ri.width), Math.round(ri.height)], artCss: [Math.round(ra.width), Math.round(ra.height)], dpr: devicePixelRatio, inkStyle: ink.style.cssText.slice(0, 120) }""")
        await pg.screenshot(path=S + 'zi1.png')
        print('zoom', z0, '->', z1); print(info); print(errs[:3]); await b.close()
asyncio.run(main())
