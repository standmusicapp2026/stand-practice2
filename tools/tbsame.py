# A text box looks the same while it is typed as once it is on the page: for every ready-made style, the
# words in the same place, at the same size, wrapped the same way (nothing jumps when you finish typing),
# and a box turned at an angle is typed at that angle. Pictures of the place: empty, typing, done.
import asyncio, os, sys, io
from playwright.async_api import async_playwright
from PIL import Image, ImageChops
PORT = os.environ.get('PORT', '8765'); SHOT = os.environ.get('SHOT'); SP = os.environ.get('SP', '/tmp'); ONLY = os.environ.get('ONLY')
TOL = float(os.environ.get('TOL', '3'))
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
TXT = 'Allegro ma non troppo, sempre cantabile e dolce'
def ink(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L').point(lambda v: 255 if v > 60 else 0)
    return d, d.getbbox()
async def run(b, name, vw, vh):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
    await pg.add_style_tag(content='.tb-edit { caret-color: transparent !important; border-color: transparent !important; } .sel-box, .sel-handle, .sel-h, .selbar, #tbBar, #inkbar, #textPop { visibility: hidden !important; }')
    styles = await J("const { TEXT_STYLES } = await import('/js/inkx.js'); return TEXT_STYLES.map((t) => t.k);")
    if ONLY: styles = [s for s in styles if s in ONLY.split(',')]
    res = []
    for k in styles + ['rot']:
        kk = 'body' if k == 'rot' else k
        await J("window.__tb.add(a, 'x'); await sleep(50); const t = window.__tb.edit; t.ta.value = ''; window.__tb.finish(); window.__tb.clear(); await sleep(150);", kk)   # (fonts loaded)
        await J("window.__tb.add(a[0], a[1]); await sleep(60);" + ("window.__tb.change({ rot: 0.35 });" if k == 'rot' else "") + " await document.fonts.ready; await sleep(350);", [kk, TXT])
        r = await J("const t = window.__tb.edit; const q = t.ta.getBoundingClientRect(); return [q.left, q.top, q.width, q.height];")
        m = 60; clip = {'x': max(0, r[0] - m), 'y': max(0, r[1] - m), 'width': min(vw - max(0, r[0] - m), r[2] + 2 * m), 'height': min(vh - max(0, r[1] - m), r[3] + 2 * m)}
        typing = Image.open(io.BytesIO(await pg.screenshot(clip=clip)))
        # what the page shows with the box hidden (the empty place)
        await J("const t = window.__tb.edit; t.ta.style.visibility = 'hidden'; await sleep(120);")
        empty = Image.open(io.BytesIO(await pg.screenshot(clip=clip)))
        await J("const t = window.__tb.edit; t.ta.style.visibility = ''; window.__tb.finish(); window.__tb.clear(); await sleep(400);")
        done = Image.open(io.BytesIO(await pg.screenshot(clip=clip)))
        mt, bt = ink(typing, empty); md, bd = ink(done, empty)
        if SHOT:
            W, H = typing.size; o = Image.new('RGB', (W, H * 2 + 10), 'red'); o.paste(typing, (0, 0)); o.paste(done, (0, H + 10)); o.save(f'{SP}/tbsame_{name}_{k}.png')
        if not bt or not bd: check(False, f'{name} {k}: words seen typing {bt} and done {bd}'); continue
        s = 2  # (device pixels)
        d = [round((bd[i] - bt[i]) / s, 1) for i in range(4)]
        both = ImageChops.multiply(mt, md).getbbox()
        over = sum(1 for v in ImageChops.multiply(mt, md).getdata() if v) / max(1, sum(1 for v in md.getdata() if v))
        res.append((k, d, round(over, 2)))
        check(max(abs(x) for x in d) <= TOL, f'{name} {k}: the same place and size typing and done (left, top, right, bottom moved {d} px; overlap {over:.2f})')
        # an item left on the page for the next: take it off
        await J("const e = window.__entries().find((p) => p.layer && p.layer.items.some((s) => s.t === 'tb')); if (e) e.layer.setItems(e.layer.items.filter((s) => s.t !== 'tb')); await sleep(150);")
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for d in [('ipad-portrait', 820, 1180), ('iphone', 393, 852)][:int(os.environ.get('ND', '2'))]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
