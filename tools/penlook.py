import asyncio
from playwright.async_api import async_playwright
exec(open('smoke.py').read().split('async def main')[0])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1024,'height':1366}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        await pg.set_input_files('#importInput', FIX + 'vector8.pdf'); await pg.wait_for_timeout(3000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500); await pg.evaluate("() => { document.querySelectorAll('.tour-skip').forEach(b=>b.click()); document.querySelectorAll('.tour, .tour-card').forEach(t=>t.remove()); }"); await pg.wait_for_timeout(400)
        await pg.evaluate("() => { document.querySelector('#zoomBtn').click(); document.querySelector('#zoomPresets button:last-child').click(); }"); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => document.querySelector('#inkBtn').click()"); await pg.wait_for_timeout(800)
        x, y = 500, 600
        pts = [[x + (i % 2) * 0.6 + (0 if i < 40 else 3), y + (i * 6 if i < 40 else (79 - i) * 6)] for i in range(80)]
        await pg.evaluate("""async (pts) => {
          const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
          const t = document.elementFromPoint(pts[0][0], pts[0][1]);
          const ev = (type, [x, y], pr) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: pr, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown', pts[0], 0.3);
          let i = 0; for (const q of pts.slice(1)) { ev('pointermove', q, 0.3 + 0.4 * Math.sin(i++ / 6) ** 2); await sleep(16); }
          window.__penUp = () => ev('pointerup', pts[pts.length - 1], 0);
        }""", pts)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/pen_live.png', clip={'x': x-60, 'y': y-30, 'width': 120, 'height': 300})
        await pg.evaluate("window.__penUp()"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/pen_done.png', clip={'x': x-60, 'y': y-30, 'width': 120, 'height': 300})
        print(await pg.evaluate("() => document.querySelector('.zoom-pill, #zoomVal')?.textContent"))
        await b.close()
asyncio.run(main())
