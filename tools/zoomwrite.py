# Writing, then at once a little zoom out with two fingers (real touches, CDP), at an iPad's speed (CPU
# 4x slower): the zoom must be as smooth as when nothing was just written — no long frame as it
# starts, while it runs, or as it ends. A notebook and a score, zoomed in and at the page's size.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); THR = float(os.environ.get('THR', '4')); PROF = os.environ.get('PROF')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
TRACK = """() => { window.__trk = []; let run = true; const f = (t) => { window.__trk.push(t); if (run) requestAnimationFrame(f); }; requestAnimationFrame(f); window.__trkStop = () => { run = false; }; }"""
async def run(b, name, vw, vh, zoomed):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
    # the pen, writing mode on
    await J("const pen = document.querySelector('.ink-tool[data-tool=pen]'); if (pen) pen.click(); await sleep(300);")
    cdp = await ctx.new_cdp_session(pg)
    async def pinch(spread0, spread1, steps=14):
        cx, cy = vw / 2, vh * 0.5
        pts = lambda s: [{'x': cx - s / 2, 'y': cy, 'id': 1}, {'x': cx + s / 2, 'y': cy, 'id': 2}]
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pts(spread0)})
        for k in range(1, steps + 1):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': pts(spread0 + (spread1 - spread0) * k / steps)}); await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    if zoomed: await pinch(160, 420); await pg.wait_for_timeout(1500)
    z0 = await J("return document.querySelector('#zoomPill')?.textContent || ''")
    async def write(n):
        # lines of handwriting with the Pencil, as pointer events where the page is
        for l in range(n):
            y = vh * (0.3 + 0.05 * l)
            await J("""const [x0, y, w] = a; const t = document.elementFromPoint(x0, y); const ev = (ty, x) => t.dispatchEvent(new PointerEvent(ty, { bubbles: true, cancelable: true, pointerId: 70, pointerType: 'pen', isPrimary: true, clientX: x, clientY: y + Math.sin(x / 9) * 6, pressure: ty === 'pointerup' ? 0 : 0.5, buttons: ty === 'pointerup' ? 0 : 1 }));
              ev('pointerdown', x0); for (let i = 1; i <= 40; i++) { ev('pointermove', x0 + w * i / 40); await new Promise((r) => requestAnimationFrame(r)); } ev('pointerup', x0 + w);""", [vw * 0.2, y, vw * 0.5])
    def frames(trk):
        d = [b2 - a for a, b2 in zip(trk, trk[1:])]
        return {'n': len(d), 'long': sum(1 for x in d if x > 50), 'over33': sum(1 for x in d if x > 34), 'max': round(max(d or [0])), 'sum_over': round(sum(max(0, x - 17) for x in d))}
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': THR})
    res = {}
    for label, n in [('nothing written', 0), ('just written', 4)]:
        if n: await write(n)
        if PROF and n: await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', {'interval': 200}); await cdp.send('Profiler.start')
        await pg.evaluate(TRACK)
        await pinch(420, 330)            # a little zoom out
        await pg.wait_for_timeout(1200); await pg.evaluate("window.__trkStop()")
        res[label] = frames(await pg.evaluate("window.__trk"))
        if PROF and n:
            prof = (await cdp.send('Profiler.stop'))['profile']; nodes = {x['id']: x for x in prof['nodes']}; selft = {}
            for sid, d in zip(prof['samples'], prof['timeDeltas']):
                cf = nodes[sid]['callFrame']; k = cf['functionName'] + ' ' + cf['url'].split('/')[-1] + ':' + str(cf['lineNumber']); selft[k] = selft.get(k, 0) + d
            for k, v in sorted(selft.items(), key=lambda kv: -kv[1])[:20]: print('SELF', round(v / 1000), k)
        await pinch(330, 420); await pg.wait_for_timeout(1500)   # (back as it was)
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    tag = f'{name} ' + ('zoomed in' if zoomed else 'page size') + f' ({z0.split()[0] if z0 else "?"})'
    a, w = res['nothing written'], res['just written']
    print('     ', tag, res)
    check(w['long'] <= max(1, a['long']), f'{tag}: zoom out just after writing: no long frames more than without writing ({w["long"]} vs {a["long"]}, longest {w["max"]} vs {a["max"]} ms)')
    check(w['sum_over'] <= a['sum_over'] * 1.5 + 60, f'{tag}: as smooth as without writing (time lost to slow frames {w["sum_over"]} vs {a["sum_over"]} ms)')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for d in [('ipad-portrait', 820, 1180), ('ipad-land', 1180, 820)][:int(os.environ.get('ND', '2'))]:
            for zm in (True, False): await run(b, *d, zm)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
