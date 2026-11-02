# Compose: after a pinch, the point of the music that was between the fingers is still under them
import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1180,'height':820}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); " + js + " }", a)
        await J("await E.createComposition({ title: 'Zoom', insts: ['violin', 'cello', 'piano'], time: [4, 4], bars: 80 }); await sleep(1500);")
        # scroll to the third page, pinch there
        res = []
        for (k, s) in [(1.6, 'in'), (0.7, 'out')]:
            r = await J("""const sc = document.querySelector('#cpScroll'); const pages = [...document.querySelectorAll('.cp-page')];
              const target = pages[Math.min(2, pages.length - 1)]; sc.scrollTop = target.offsetTop - 80; await sleep(300);
              const sr = sc.getBoundingClientRect(); const cx = sr.left + sr.width * 0.45, cy = sr.top + sr.height * 0.55;
              // the point of the music under the fingers: its page and place on it
              const pr = target.getBoundingClientRect(); const u = (cx - pr.left) / pr.width, v = (cy - pr.top) / pr.height;
              const T = (id, x, y) => new Touch({ identifier: id, target: sc, clientX: x, clientY: y });
              const fire = (type, ts) => sc.dispatchEvent(new TouchEvent(type, { touches: ts, targetTouches: ts, changedTouches: ts, bubbles: true, cancelable: true }));
              const d0 = 100, K = a.k, steps = 12, mx = 30, my = 20;
              fire('touchstart', [T(1, cx - d0 / 2, cy), T(2, cx + d0 / 2, cy)]);
              for (let i = 1; i <= steps; i++) { const d = d0 * (1 + (K - 1) * i / steps), ox = mx * i / steps, oy = my * i / steps; fire('touchmove', [T(1, cx + ox - d / 2, cy + oy), T(2, cx + ox + d / 2, cy + oy)]); await sleep(16); }
              fire('touchend', []); await sleep(800);
              const pr2 = target.getBoundingClientRect(); const ex = pr2.left + u * pr2.width, ey = pr2.top + v * pr2.height;
              return { zoom: document.querySelector('#cpZoomVal').textContent, off: [Math.round(ex - (cx + mx)), Math.round(ey - (cy + my))] };""", {'k': k})
            res.append((s, r))
        for s, r in res: print('pinch', s, r)
        print(errs[:3]); await b.close()
asyncio.run(main())
