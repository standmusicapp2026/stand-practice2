# Writing zoomed in: is the line as sharp after the Pencil lifts as while it is drawn?
# Pixel test: the stroke is photographed (screen pixels, device scale) with the pen still down,
# and again 0.3 s, 1.5 s and 3 s after it lifts, each minus a photo of the same place before the
# stroke. Sharpness = mean gradient of the stroke; blur = softer edges = lower gradient, more grey.
# Zoom by real pinch (Chromium: CDP touch) and by the zoom presets (both browsers).
import asyncio, os, sys, io
import numpy as np
from PIL import Image
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
SHOT = os.environ.get('SHOT', '')
FIX = '/home/claude/fixtures/vector8.pdf'
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

PEN_DOWN = """async (pts) => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t = document.elementFromPoint(pts[0][0], pts[0][1]); window.__penT = t;
  const ev = (type, [x, y]) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y, pressure: 0.5, buttons: 1 }));
  ev('pointerdown', pts[0]); for (const q of pts.slice(1)) { ev('pointermove', q); await sleep(16); } await sleep(120); }"""
PEN_UP = """(p) => { window.__penT.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, composed: true, pointerId: 77, pointerType: 'pen', isPrimary: true, clientX: p[0], clientY: p[1], pressure: 0, buttons: 0 })); }"""

def arr(png):
    return np.asarray(Image.open(io.BytesIO(png)).convert('L'), dtype=np.float32)
def measure(base, img):
    d = np.clip(base - img, 0, 255)        # the stroke alone (darker than before)
    mask = d > 40
    if mask.sum() < 20: return None
    gy, gx = np.gradient(d)
    g = np.hypot(gx, gy)
    edge = g[(d > 8)]
    soft = ((d > 8) & (d < 0.5 * d.max())).sum() / max(1, (d > 8).sum())   # share of grey fringe
    return {'ink': float(d.sum() / 255), 'grad': float(edge.mean()), 'soft': float(soft)}

async def pinch(pg, cx, cy, frm, to):
    cdp = await pg.context.new_cdp_session(pg)
    steps = 14
    async def tp(t, d):
        await cdp.send('Input.dispatchTouchEvent', {'type': t, 'touchPoints': [] if t == 'touchEnd' else [{'x': cx - d, 'y': cy, 'id': 1}, {'x': cx + d, 'y': cy, 'id': 2}]})
    await tp('touchStart', frm)
    for i in range(1, steps + 1):
        await tp('touchMove', frm + (to - frm) * i / steps); await pg.wait_for_timeout(16)
    await tp('touchEnd', to)

async def run(b, name, vw, vh, dpr, how, z):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=dpr, has_touch=True)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); [...document.querySelectorAll('.ask-back button')].find((b) => /Not now/.test(b.textContent))?.click();")
    await pg.set_input_files('#importInput', [FIX])
    await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
    await J("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(3500)
    sr = await J("const r = document.querySelector('#stage').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]")
    cx, cy = sr[0] + sr[2] / 2, sr[1] + sr[3] / 2
    if how == 'pinch':
        await pinch(pg, cx, cy, 60, 60 * z)
    else:
        await J("document.querySelector('#zoomBtn').click(); await sleep(150); const b = document.querySelector('#zoomPresets [data-z=\"' + a + '\"]'); b && b.click(); await sleep(150); document.querySelector('#zoomBtn').click();", str(z))
    await pg.wait_for_timeout(2500)
    zs = await J("return document.querySelector('#zoomPill')?.textContent || ''")
    await J("document.querySelector('#inkBtn').click(); await sleep(500);")
    pts = [[cx - 120 + i * 6, cy - 30 + 25 * np.sin(i / 5)] for i in range(40)]
    pts = [[float(x), float(y)] for x, y in pts]
    clip = {'x': cx - 140, 'y': cy - 80, 'width': 280, 'height': 110}
    base = arr(await pg.screenshot(clip=clip))
    await pg.evaluate(PEN_DOWN, pts)
    live = measure(base, arr(await pg.screenshot(clip=clip)))
    await pg.evaluate(PEN_UP, pts[-1])
    res = {}
    for t in (300, 1500, 3500):
        await pg.wait_for_timeout(t - (sum(int(k) for k in res) if False else 0))
        res[t] = arr(await pg.screenshot(clip=clip))
    if SHOT:
        Image.fromarray(np.uint8(res[3500])).save(f'{SHOT}/inkblur_{name}_{how}{z}.png')
    m = {t: measure(base, v) for t, v in res.items()}
    tag = f'{name} {how} {z}x ({zs.split()[0] if zs else "?"})'
    if not live or not all(m.values()):
        check(False, f'{tag}: the stroke shows {live} {m}'); await ctx.close(); return
    worst = min(m.values(), key=lambda q: q['grad'])
    ratio = worst['grad'] / live['grad']
    check(ratio > 0.9 and worst['soft'] < live['soft'] + 0.08 and abs(worst['ink'] - live['ink']) / live['ink'] < 0.25,
          f'{tag}: as sharp after the pen lifts as while drawing (gradient {ratio:.2f} of live; grey fringe {live["soft"]:.2f} -> {worst["soft"]:.2f}; ink {live["ink"]:.0f} -> {worst["ink"]:.0f})')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        devs = [('ipad', 1180, 820, 2), ('ipad-pro13', 1376, 1032, 2), ('ipad-portrait', 820, 1180, 2), ('ipad-mini', 744, 1133, 2), ('ipad-pro11-land', 1210, 834, 2)]
        only = sys.argv[1:]
        for d in devs:
            if only and d[0] not in only: continue
            for how, z in ([('pinch', 2), ('pinch', 3.2)] if BR == 'chromium' else []) + [('preset', 2), ('preset', 3)]:
                await run(b, d[0], d[1], d[2], d[3], how, z)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
