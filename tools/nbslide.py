# (nbslide) A notebook a page at a time: the page goes with the finger sideways; let go far enough (or
# flicked) the next page slides in after it, smoothly; not far enough, it slides back; the first page
# gives only a little; no page left behind on the screen; no errors. On iPad and iPhone sizes.
import asyncio, json, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); THR = int(os.environ.get('THR', '4'))
OK = []
def check(name, cond, info=''):
    print(('ok   ' if cond else 'FAIL ') + name + (' ' + str(info) if info != '' else '')); OK.append(bool(cond))
DRAG = """async (a) => { const st = document.querySelector('#stage'); const gaps = []; let last = performance.now(), run = true, maxGhost = 0, seenGhost = false;
  const loop = () => { const t = performance.now(); gaps.push(t - last); last = t; const g = document.querySelectorAll('#stage .nb-ghost').length; if (g) seenGhost = true; maxGhost = Math.max(maxGhost, g); if (run) requestAnimationFrame(loop); }; requestAnimationFrame(loop);
  const ev = (t, x, id) => (t === 'pointerdown' ? st : window).dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, pointerId: id, pointerType: 'touch', clientX: x, clientY: 500, width: 20, height: 20, buttons: t === 'pointerup' ? 0 : 1 }));
  const p0 = window.__entries()[0].index; const x0 = a.x0, id = 70 + Math.floor(Math.random() * 1000);
  ev('pointerdown', x0, id); let mid = null;
  for (let i = 1; i <= a.n; i++) { await new Promise(r => setTimeout(r, a.ms)); ev('pointermove', x0 + a.dx * i / a.n, id); if (i === a.n) { await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); const sp = document.querySelector('#stage .spread:not(.nb-ghost)'); mid = sp ? sp.style.transform : ''; } }
  ev('pointerup', x0 + a.dx, id); await new Promise(r => setTimeout(r, 700)); run = false;
  const g = gaps.slice(2).sort((x, y) => x - y);
  const sp = document.querySelectorAll('#stage .spread'), r = sp[sp.length - 1].getBoundingClientRect();
  return { p0, p1: window.__entries()[0].index, mid, seenGhost, maxGhost, left: document.querySelectorAll('#stage .spread').length, x: Math.round(r.left + r.width / 2 - innerWidth / 2), g90: +g[Math.floor(g.length * 0.9)].toFixed(1), max: Math.round(g[g.length - 1]), long: g.filter((x) => x > 50).length }; }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for (w, h, nm) in [(820, 1180, 'ipad'), (1180, 820, 'ipad-land'), (390, 844, 'iphone')]:
            ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
            await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }"); await pg.wait_for_timeout(500)
            await pg.evaluate("""async () => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); document.querySelector('#newNotebookBtn').click(); await sleep(1500);
              document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);
              const { db } = await import('/js/db.js'); const fs = await db.all('files'); const f = fs.find((x) => x.kind === 'paper'); f.pages = 6; await db.put('files', f); }""")
            await pg.reload(); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { document.querySelector('.tour-skip')?.click(); }")
            await pg.evaluate("async () => { const c = [...document.querySelectorAll('#grid .card:not(.folder)')][0]; c.click(); await new Promise(r => setTimeout(r, 2500)); document.querySelector('.tour-skip')?.click(); if (document.querySelector('#inkbar') && !document.querySelector('#inkbar').hidden) document.querySelector('#inkDone')?.click(); await new Promise(r => setTimeout(r, 400)); }")
            await pg.evaluate("() => window.__scroll && window.__scroll.set(false)"); await pg.wait_for_timeout(1200)
            st = await pg.evaluate("() => ({ page: window.__entries()[0].index, inking: !!document.querySelector('#stage.inking') })")
            print(nm, 'start', st)
            cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': THR})
            # the first page: pulled right, it gives only a little and comes back
            r = await pg.evaluate(DRAG, {'x0': w * 0.3, 'dx': w * 0.5, 'n': 12, 'ms': 16})
            check(f'{nm}: the first page pulled back gives a little, stays', r['p1'] == r['p0'] == 0 and r['left'] == 1 and abs(r['x']) < 3 and 'translate(' in (r['mid'] or ''), r)
            # slow drag of 40% to the left: on to page 2, the old page slides away
            r = await pg.evaluate(DRAG, {'x0': w * 0.8, 'dx': -w * 0.4, 'n': 20, 'ms': 30})
            check(f'{nm}: pulled 40% and let go: the next page slides in', r['p1'] == r['p0'] + 1 and r['seenGhost'] and r['left'] == 1 and abs(r['x']) < 3, r)
            check(f'{nm}: smooth while sliding (4x slower CPU)', r['long'] <= 1 and r['g90'] < 34, r)
            # a short drag: back
            r = await pg.evaluate(DRAG, {'x0': w * 0.6, 'dx': -w * 0.12, 'n': 10, 'ms': 40})
            check(f'{nm}: a short slow pull goes back', r['p1'] == r['p0'] and r['left'] == 1 and abs(r['x']) < 3, r)
            # a quick flick: on
            r = await pg.evaluate(DRAG, {'x0': w * 0.7, 'dx': -w * 0.18, 'n': 5, 'ms': 12})
            check(f'{nm}: a quick flick turns', r['p1'] == r['p0'] + 1 and r['left'] == 1, r)
            # flick back to the right
            r = await pg.evaluate(DRAG, {'x0': w * 0.3, 'dx': w * 0.2, 'n': 5, 'ms': 12})
            check(f'{nm}: a quick flick back', r['p1'] == r['p0'] - 1 and r['left'] == 1, r)
            # very quick flicks one after another
            r0 = await pg.evaluate("() => window.__entries()[0].index")
            for k in range(3):
                await pg.evaluate(DRAG.replace('setTimeout(r, 700)', 'setTimeout(r, 60)'), {'x0': w * 0.7, 'dx': -w * 0.2, 'n': 4, 'ms': 10})
            await pg.wait_for_timeout(900)
            r = await pg.evaluate("() => ({ page: window.__entries()[0].index, spreads: document.querySelectorAll('#stage .spread').length, ghosts: document.querySelectorAll('.nb-ghost').length })")
            check(f'{nm}: three quick flicks, three pages on, nothing left behind', r['page'] == min(5, r0 + 3) and r['spreads'] == 1 and r['ghosts'] == 0, r)
            # the arrows on the keyboard: slide too
            await pg.keyboard.press('ArrowLeft'); await pg.wait_for_timeout(80)
            g = await pg.evaluate("() => document.querySelectorAll('.nb-ghost').length")
            await pg.wait_for_timeout(700)
            r = await pg.evaluate("() => ({ page: window.__entries()[0].index, spreads: document.querySelectorAll('#stage .spread').length })")
            check(f'{nm}: a key turns with the slide too', r['spreads'] == 1, (g, r))
            await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
            # writing still works on the page after sliding
            ok = await pg.evaluate("() => !!document.querySelector('#stage .pg canvas.ink') && document.querySelector('#stage .pg canvas.ink').width > 0")
            check(f'{nm}: the page shown has its markings layer', ok)
            check(f'{nm}: no page errors', not errs, errs[:3])
            await ctx.close()
        print('PASS' if all(OK) else 'FAIL', 'notebook pages slide')
        await b.close()
    sys.exit(0 if all(OK) else 1)
asyncio.run(main())
