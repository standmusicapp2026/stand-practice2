# A recording's video over the score: two fingers make the window bigger or smaller (as the YouTube
# video), it keeps its shape and stays on the screen; its line shows where it is and can be dragged
# to go anywhere in it (paused stays paused, playing keeps playing); double tap still zooms in.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
SHOT = os.environ.get('SHOT', '')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def touch(pg, kind, pts):
    cdp = pg._cdp
    await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i + 1} for i, (x, y) in enumerate(pts)]})

async def pinch(pg, cx, cy, d0, d1, steps=12):
    await touch(pg, 'touchStart', [(cx - d0 / 2, cy), (cx + d0 / 2, cy)])
    for k in range(1, steps + 1):
        d = d0 + (d1 - d0) * k / steps
        await touch(pg, 'touchMove', [(cx - d / 2, cy), (cx + d / 2, cy)]); await pg.wait_for_timeout(16)
    await touch(pg, 'touchEnd', [])

async def run(b, name, vw, vh):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, has_touch=True, device_scale_factor=2)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); [...document.querySelectorAll('.ask-back button')].find((b) => /Not now/.test(b.textContent))?.click();")
    await J("document.querySelector('.tile[data-tile=\"takes\"]').click(); await sleep(500);")
    await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/clip.webm'); await pg.wait_for_timeout(5000)
    await J("document.querySelector('#takeList li')?.click(); await sleep(1500); document.querySelector('#takeFloat').click(); await sleep(900);")
    on = await J("return !document.querySelector('#vfloat').hidden")
    check(on, f'{name}: the video floats over the score')
    if not on: await ctx.close(); return
    R = "const r = document.querySelector('#vfloat').getBoundingClientRect(); return [r.left, r.top, r.width, r.height];"
    r0 = await J(R)
    if BR == 'chromium':
        pg._cdp = await ctx.new_cdp_session(pg)
        cx, cy = r0[0] + r0[2] / 2, r0[1] + r0[3] * 0.4
        await pinch(pg, cx, cy, 60, 160); await pg.wait_for_timeout(300)
        r1 = await J(R)
        check(r1[2] > r0[2] * 1.5, f'{name}: two fingers apart: the window grows ({r0[2]:.0f} -> {r1[2]:.0f})')
        check(abs(r1[3] / r1[2] - r0[3] / r0[2]) < 0.02, f'{name}: it keeps its shape')
        check(r1[0] >= 3 and r1[1] >= 3 and r1[0] + r1[2] <= vw - 3 and r1[1] + r1[3] <= vh - 3, f'{name}: and stays on the screen {[round(v) for v in r1]}')
        z = await J("return document.querySelector('#takeVideo').style.transform")
        check('scale(1)' in z or 'scale' not in z, f'{name}: the picture itself is not zoomed by it ({z})')
        # very far apart: never bigger than the screen
        cx, cy = r1[0] + r1[2] / 2, r1[1] + r1[3] * 0.4
        await pinch(pg, cx, cy, 80, 900); await pg.wait_for_timeout(300)
        r2 = await J(R)
        check(r2[2] <= vw - 8 and r2[3] <= vh - 8 and r2[0] >= 3 and r2[1] >= 3, f'{name}: never bigger than the screen {[round(v) for v in r2]}')
        cx, cy = r2[0] + r2[2] / 2, r2[1] + r2[3] * 0.4
        await pinch(pg, cx, cy, 300, 40); await pg.wait_for_timeout(300)
        r3 = await J(R)
        check(r3[2] >= 199 and r3[2] < r2[2], f'{name}: fingers together: smaller, never tiny ({r3[2]:.0f})')
        if SHOT: await pg.screenshot(path=f'{SHOT}/vf_{name}.png')
    # the line: where the recording is; dragged, it goes there
    d = await J("return [window.__vfDur ? window.__vfDur() : null]")
    sc = await J("const s = document.querySelector('#vfScrub'), r = s.getBoundingClientRect(), f = document.querySelector('#vfloat').getBoundingClientRect(); return { w: r.width, inside: r.left >= f.left && r.right <= f.right && r.bottom <= f.bottom, shown: getComputedStyle(s).display !== 'none' && +getComputedStyle(s).opacity > 0.5, x: r.left, y: r.top + r.height / 2 };")
    check(sc['shown'] and sc['w'] > 120 and sc['inside'], f'{name}: the video has its line, across it {sc}')
    async def drag_to(frac):
        x0, y = sc['x'] + 4, sc['y']; x1 = sc['x'] + sc['w'] * frac
        await pg.mouse.move(x0, y); await pg.mouse.down(); await pg.mouse.move((x0 + x1) / 2, y, steps=4)
        mid = await J("const s = document.querySelector('#vfScrub'); return [s.classList.contains('on'), s.querySelector('.sc-tip').textContent]")
        await pg.mouse.move(x1, y, steps=4); await pg.mouse.up(); await pg.wait_for_timeout(900)
        return mid
    st0 = await J("const v = document.querySelector('#takeVideo'); return [v.paused, v.duration]")
    mid = await drag_to(0.6)
    st = await J("const v = document.querySelector('#takeVideo'); return [v.currentTime, v.duration, v.paused, getComputedStyle(document.querySelector('#vfScrub')).getPropertyValue('--f')]")
    check(mid[0] and ':' in mid[1], f'{name}: while dragging, the time it will go to shows {mid}')
    check(st[1] and abs(st[0] / st[1] - 0.6) < 0.08 and abs(float(st[3]) - 0.6) < 0.08, f'{name}: let go: the recording is there, and the line with it {st}')
    check(st[2] == st0[0], f'{name}: paused stays paused, playing keeps playing (before {st0[0]}, after {st[2]})')
    # playing: the line moves on by itself
    await J("document.querySelector('#vfPlay').click(); await sleep(150);")
    f1 = await J("return +getComputedStyle(document.querySelector('#vfScrub')).getPropertyValue('--f')")
    await pg.wait_for_timeout(1200)
    f2 = await J("return +getComputedStyle(document.querySelector('#vfScrub')).getPropertyValue('--f')")
    playing = await J("return !document.querySelector('#takeVideo').paused")
    check(f2 > f1 or not playing, f'{name}: playing, the line moves on ({f1:.3f} -> {f2:.3f}, playing {playing})')
    await J("document.querySelector('#vfPlay').click(); await sleep(150);")
    # double tap still zooms into the picture
    fr = await J(R)
    tx, ty = fr[0] + fr[2] * 0.4, fr[1] + fr[3] * 0.35
    for _ in range(2):
        await pg.mouse.move(tx, ty); await pg.mouse.down(); await pg.mouse.up(); await pg.wait_for_timeout(90)
    await pg.wait_for_timeout(300)
    z = await J("return document.querySelector('#takeVideo').style.transform")
    check('scale(2)' in z, f'{name}: double tap zooms into the picture ({z})')
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch(args=['--autoplay-policy=no-user-gesture-required'] if BR == 'chromium' else [])
        for d in [('ipad-land', 1180, 820), ('ipad-portrait', 820, 1180), ('ipad-pro13', 1376, 1032), ('ipad-mini', 744, 1133), ('ipad-mini-land', 1133, 744)]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
