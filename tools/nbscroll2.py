# A notebook scrolled down, moved by real touches (CDP), as a hand does: quick flicks, a flick again
# while it still runs, very quick ones; at an iPad's speed (CPU 4x slower). It must run on smoothly and
# slow down evenly (never stop of itself in the middle), a second flick goes on faster, and no frame is
# long. Pages written on (markings) are among them.
import asyncio, json, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); THR = float(os.environ.get('THR', '4'))
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
TRACK = """() => { window.__trk = []; let run = true; const st = document.querySelector('#stage');
  const f = () => { const col = st.querySelector('.scroll-col') || st.querySelector('.spread'); const r = col ? col.getBoundingClientRect() : { top: 0 };
    window.__trk.push([performance.now(), r.top]); if (run) requestAnimationFrame(f); }; requestAnimationFrame(f); window.__trkStop = () => { run = false; }; }"""
async def run(b, name, vw, vh):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }"); await pg.wait_for_timeout(500)
    await pg.evaluate("""async () => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); document.querySelector('#newNotebookBtn').click(); await sleep(1500);
      document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);
      const { db } = await import('/js/db.js'); const fs = await db.all('files'); const f = fs.find((x) => x.kind === 'paper'); f.pages = 30; await db.put('files', f);
      // writing on every other page: lines of handwriting
      const sc = (await db.all('scores')).find((s) => s.fileId === f.id);
      for (let p = 0; p < 30; p += 2) { const items = []; for (let l = 0; l < 14; l++) { const pts = []; for (let i = 0; i < 40; i++) pts.push([0.1 + i * 0.02, 0.1 + l * 0.06 + Math.sin(i / 2) * 0.008, 0.5]); items.push({ t: 'pen', c: '#1d2f6f', s: 0.002, a: 1, p: pts }); }
        await db.put('ink', { key: sc.id + ':' + p, items }); } }""")
    await pg.reload(); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => { document.querySelector('.tour-skip')?.click(); }")
    await pg.evaluate("async () => { const c = [...document.querySelectorAll('#grid .card:not(.folder)')][0]; c.click(); await new Promise(r => setTimeout(r, 2500)); document.querySelector('.tour-skip')?.click(); }")
    await pg.evaluate("() => window.__scroll.set(true)"); await pg.wait_for_timeout(2500)
    cdp = await ctx.new_cdp_session(pg)
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': THR})
    async def flick(dy, ms, x=None):
        x = x or vw / 2; y0 = vh * 0.7 if dy < 0 else vh * 0.3; steps = max(4, int(ms / 16))
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0, 'id': 7}]})
        for i in range(1, steps + 1):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + dy * i / steps, 'id': 7}]}); await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    def analyse(trk, t_up):
        # after letting go: speed frame by frame (px/ms); it must fall evenly, not drop to nothing at once while still fast
        pts = [(t, y) for t, y in trk if t >= t_up]
        sp = []
        for (t0, y0), (t1, y1) in zip(pts, pts[1:]):
            if t1 - t0 > 0: sp.append((t1 - t0, abs(y1 - y0) / (t1 - t0)))
        v0 = max([v for _, v in sp[:4]] or [0])
        stops = 0
        for i in range(1, len(sp) - 2):
            a, b2, c = sp[i - 1][1], sp[i][1], sp[i + 1][1]
            if a > 0.35 and b2 < a * 0.25 and c < a * 0.25: stops += 1   # (fast, then all at once nothing)
        frames = [d for d, _ in sp]
        dist = abs(pts[-1][1] - pts[0][1]) if pts else 0
        return { 'v0': round(v0, 2), 'stops': stops, 'long': sum(1 for d in frames if d > 50), 'max': round(max(frames or [0])), 'dist': round(dist) }
    res = {}
    for label, dy, ms in [('quick flick', -500, 90), ('very quick flick', -700, 60), ('flick back up', 500, 90)]:
        await pg.evaluate(TRACK); t = await pg.evaluate("performance.now()")
        await flick(dy, ms); t_up = await pg.evaluate("performance.now()")
        await pg.wait_for_timeout(2600); await pg.evaluate("window.__trkStop()")
        res[label] = analyse(await pg.evaluate("window.__trk"), t_up)
    # two flicks one after the other: the second, while it still runs, carries it further than one
    await pg.evaluate(TRACK); await flick(-500, 90); await pg.wait_for_timeout(250); y_mid = await pg.evaluate("window.__trk[window.__trk.length - 1][1]")
    await flick(-500, 90); t_up = await pg.evaluate("performance.now()"); await pg.wait_for_timeout(2600); await pg.evaluate("window.__trkStop()")
    trk = await pg.evaluate("window.__trk"); two = analyse(trk, t_up); two['total'] = round(abs(trk[-1][1] - trk[0][1]))
    res['two flicks'] = two
    await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    for k, r in res.items():
        check(r['stops'] == 0 and r['dist'] > 500, f'{name}: {k}: runs on and slows down evenly, never stops of itself {r}')
        check(r['long'] <= 2, f'{name}: {k}: smooth (frames over 50 ms: {r["long"]}, longest {r["max"]} ms)')
    check(res['two flicks']['total'] > res['quick flick']['dist'] * 1.4, f'{name}: a second flick while it runs carries it further ({res["two flicks"]["total"]} vs {res["quick flick"]["dist"]})')
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for d in [('ipad-portrait', 820, 1180), ('ipad-land', 1180, 820)]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
