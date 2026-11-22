# (trimtest) Studio's trimmer, as in Photos: pictures of the video along the strip, a yellow frame
# with a handle at each end; a handle dragged trims; held still, the strip opens out around it (a few
# seconds across the whole width) for the exact moment, the handle staying under the finger, and
# closes again when let go. On an iPad and on an iPhone.
import asyncio, json, sys
from playwright.async_api import async_playwright
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad'
async def run(b, name, vp, ua):
    ctx = await b.new_context(viewport=vp, device_scale_factor=2, user_agent=ua, has_touch=True)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
    await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
    await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); document.querySelectorAll('.ask-back button').forEach(b=>/Not now/.test(b.textContent)&&b.click()); }")
    await pg.set_input_files('#takeImportFile', '/home/claude/dragon/4M30 clarinetes.webm')
    for _ in range(60):
        if await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0 && !!t[0].pcm; }"): break
        await pg.wait_for_timeout(1000)
    tid = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('takes'))[0].id; }")
    await pg.evaluate("async (id) => { const S = await import('/js/studio.js'); await S.openStudio(id); document.querySelector('.tour-skip')?.click(); }", tid)
    # (the pictures along the strip come in the background)
    for _ in range(60):
        n = await pg.evaluate("() => { const c = document.querySelector('#stWave'); const g = c.getContext('2d'); const d = g.getImageData(c.width * 0.5 | 0, c.height * 0.3 | 0, 1, 1).data; return d[0] + d[1] + d[2]; }")
        if n > 30: break
        await pg.wait_for_timeout(500)
    strip = n > 30
    R = await pg.evaluate("() => { const r = document.querySelector('#stTrimR').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }")
    dur = await pg.evaluate("async () => (await import('/js/studio.js'))._studio.dur")
    # a plain drag of the right handle to the left
    await pg.mouse.move(R['x'], R['y']); await pg.mouse.down(); await pg.wait_for_timeout(80)
    for k in range(10): await pg.mouse.move(R['x'] - 8 * (k + 1), R['y']); await pg.wait_for_timeout(16)
    tip = await pg.evaluate("() => !document.querySelector('#stTrimTip').hidden && document.querySelector('#stTrimTip').textContent")
    await pg.mouse.up(); await pg.wait_for_timeout(200)
    b1 = await pg.evaluate("async () => (await import('/js/studio.js'))._studio.P.trim.b")
    # held still: opens out; the handle stays under the finger; a move then is fine
    R = await pg.evaluate("() => { const r = document.querySelector('#stTrimR').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }")
    await pg.mouse.move(R['x'], R['y']); await pg.mouse.down(); await pg.wait_for_timeout(700)
    z = await pg.evaluate("async () => { const S = await import('/js/studio.js'); const v = S._studio.tv; const r = document.querySelector('#stTrimR').getBoundingClientRect(); return { tv: v, hx: r.left + r.width / 2, zoomed: document.querySelector('.st-media').classList.contains('zoomed') }; }")
    await pg.screenshot(path=f'{SP}/trim-{name}-zoom.png')
    under = abs(z['hx'] - R['x']) < 12
    for k in range(10): await pg.mouse.move(R['x'] - 6 * (k + 1), R['y']); await pg.wait_for_timeout(16)
    b2 = await pg.evaluate("async () => (await import('/js/studio.js'))._studio.P.trim.b")
    await pg.mouse.up(); await pg.wait_for_timeout(400)
    after = await pg.evaluate("async () => { const S = await import('/js/studio.js'); return { tv: S._studio.tv, zoomed: document.querySelector('.st-media').classList.contains('zoomed'), tip: document.querySelector('#stTrimTip').hidden }; }")
    await pg.screenshot(path=f'{SP}/trim-{name}.png')
    span = (z['tv']['b'] - z['tv']['a']) if z['tv'] else None
    fine = (b1 - b2)
    print(name, json.dumps({'strip': strip, 'dur': round(dur, 2), 'b1': round(b1, 2), 'tip': tip, 'span': span and round(span, 2), 'under': under, 'hx': round(z['hx']), 'x': round(R['x']), 'fine': round(fine, 3), 'after': after}))
    ok = strip and b1 < dur - 1 and tip and span and span <= 8.01 and z['zoomed'] and under and 0 < fine < 1.2 and after['tv'] is None and not after['zoomed'] and after['tip']
    print('PASS' if ok and not errs else 'FAIL', name, 'trimmer: drag, hold to open out, let go', errs[:2])
    await ctx.close()
    return ok and not errs
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        a = await run(b, 'ipad', {'width': 1180, 'height': 820}, None)
        c = await run(b, 'phone', {'width': 390, 'height': 844}, 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15')
        await b.close()
        print('PASS' if a and c else 'FAIL', 'trimmer on iPad and iPhone')
asyncio.run(main())
