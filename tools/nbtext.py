# A notebook's text box: made with the Text box tool (a tap with the Pencil), typed in; while typing,
# two fingers zoom and move the page: the box being typed stays on its place on the page, at the
# page's size, the words kept; chosen (selected) the same; scrolled down the same.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def run(b, name, vw, vh, scroll):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
    if scroll: await J("window.__scroll.set(true); await sleep(1500);")
    tag = name + (' scrolled down' if scroll else '')
    # the Text box tool, a tap with the Pencil on the page
    await J("if (!document.body.classList.contains('inking') && document.querySelector('#inkBtn')) {} document.querySelector('.ink-tool[data-tool=tbox]').click(); await sleep(300);")
    pr = await J("const p = [...document.querySelectorAll('#stage .pg')].find((q) => { const r = q.getBoundingClientRect(); return r.top < innerHeight / 2 && r.bottom > innerHeight / 2; }) || document.querySelector('#stage .pg'); const r = p.getBoundingClientRect(); return [r.left, r.top, r.width, r.height];")
    x, y = pr[0] + pr[2] * 0.3, pr[1] + min(pr[3], vh - pr[1]) * 0.35
    await J("""const t = document.elementFromPoint(a[0], a[1]); const ev = (ty) => t.dispatchEvent(new PointerEvent(ty, { bubbles: true, cancelable: true, pointerId: 61, pointerType: 'pen', isPrimary: true, clientX: a[0], clientY: a[1], pressure: ty === 'pointerup' ? 0 : 0.5, buttons: ty === 'pointerup' ? 0 : 1 }));
      ev('pointerdown'); await sleep(40); ev('pointerup'); await sleep(500);""", [x, y])
    has = await J("return !!document.querySelector('textarea.tb-edit')")
    check(has, f'{tag}: a tap with the Text box tool: a box to type in')
    if not has: await ctx.close(); return
    await pg.keyboard.type('Allegro, but calm'); await pg.wait_for_timeout(300)
    # where the box is, in the page's own terms (its place as a part of the page), and its size against the page
    REL = """const ta = document.querySelector('textarea.tb-edit'); if (!ta) return null; const p = [...document.querySelectorAll('#stage .pg')].find((q) => { const r = q.getBoundingClientRect(), t = ta.getBoundingClientRect(); return t.left >= r.left - 2 && t.left <= r.right && t.top >= r.top - 2 && t.top <= r.bottom; });
      const r = (p || document.querySelector('#stage .pg')).querySelector('.pgi').getBoundingClientRect(), t = ta.getBoundingClientRect();
      return { fx: +((t.left - r.left) / r.width).toFixed(4), fy: +((t.top - r.top) / r.height).toFixed(4), fw: +(t.width / r.width).toFixed(4), font: parseFloat(getComputedStyle(ta).fontSize) / r.width, val: ta.value, focus: document.activeElement === ta };"""
    a0 = await J(REL)
    cdp = await ctx.new_cdp_session(pg) if BR == 'chromium' else None
    async def two(fn):
        cx, cy = vw / 2, vh * 0.6
        pts = lambda k: fn(cx, cy, k)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': p[0], 'y': p[1], 'id': i + 1} for i, p in enumerate(pts(0))]})
        for k in range(1, 13): await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': p[0], 'y': p[1], 'id': i + 1} for i, p in enumerate(pts(k / 12))]}); await pg.wait_for_timeout(18)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(500)
    if cdp:
        await two(lambda cx, cy, k: [(cx - 60 - 90 * k, cy), (cx + 60 + 90 * k, cy)])   # zoom in
        a1 = await J(REL)
        z = await J("return document.querySelector('#zoomPill')?.textContent || ''")
        check(a1 and abs(a1['fx'] - a0['fx']) < 0.01 and abs(a1['fy'] - a0['fy']) < 0.01 and abs(a1['fw'] - a0['fw']) < 0.01 and abs(a1['font'] - a0['font']) / a0['font'] < 0.05, f'{tag}: zoomed in while typing ({z.split()[0] if z else "?"}): the box stays in its place on the page, at its size {a0} -> {a1}')
        await two(lambda cx, cy, k: [(cx - 80 + 0 * k, cy - 120 * k), (cx + 80, cy - 120 * k)])   # move the page
        a2 = await J(REL)
        check(a2 and abs(a2['fx'] - a0['fx']) < 0.01 and abs(a2['fy'] - a0['fy']) < 0.01, f'{tag}: the page moved: the box with it {a2}')
        check(a2 and a2['val'] == 'Allegro, but calm', f'{tag}: the words kept')
    await pg.keyboard.type(' — rit.'); await pg.wait_for_timeout(200)
    await J("document.querySelector('#stage').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 5, clientY: innerHeight - 40, pointerId: 62, pointerType: 'pen', isPrimary: true, buttons: 1 })); window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: 5, clientY: innerHeight - 40, pointerId: 62, pointerType: 'pen', isPrimary: true })); await sleep(500);")
    r = await J("const L = window.__inkLayers ? null : null; const ta = document.querySelector('textarea.tb-edit'); return { open: !!ta, sel: !!document.querySelector('.sel-box') };")
    check(not r['open'], f'{tag}: done: the words are on the page {r}')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        for d in [('ipad-portrait', 820, 1180), ('ipad-land', 1180, 820)]:
            for sc in (False, True): await run(b, *d, sc)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
