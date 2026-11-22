# Studio: the bars on the line, put right by hand. Every barline shown over the music; a tap where a
# bar begins adds one (on the barline printed there), a line dragged moves, a line tapped can be
# removed; Undo, Back to as read, Cancel. Done: the bars left as they were keep their times to the
# hundredth (and the way through them), a new barline gets the moment the music passed it, a barline
# taken away leaves its moment inside the bar. On iPads and iPhones, both ways round: it all fits,
# the Remove button is on the screen, nothing goes sideways.
import asyncio, os, sys, json
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
src = open('/home/claude/tools/studiomm.py').read()
RENDER = src[src.index('RENDER = """') + 11:src.index('}"""', src.index('RENDER = """')) + 1]
UNIT = """async () => { const S = await import('/js/studio.js');
  // three bars on one line, two on the next; times measured, notes heard in bar 2
  const bars = [{ x0: 0, x1: 100, seg: 0 }, { x0: 100, x1: 200, seg: 0 }, { x0: 200, x1: 300, seg: 0 }, { x0: 320, x1: 420, seg: 1 }, { x0: 420, x1: 520, seg: 1 }];
  const o = { layout: { bars, notes: [{ bar: 1, x: 150 }, { bar: 3, x: 330 }, { bar: 4, x: 470 }], events: [] }, times: [1, 2, 3.5, 4, 5, 6], knots: [[], [[0.3, 0.5]], [], [], []], synced: 'tap' };
  const R = [];
  // the same bars: nothing changes
  let r = S.rebar(o, bars.map((b) => ({ ...b }))); R.push({ name: 'same', times: r.times, knots: r.knots });
  // bar 2 split where its heard note is (x 150, heard at 2 + 0.3 * 1.5)
  r = S.rebar(o, [bars[0], { x0: 100, x1: 150, seg: 0 }, { x0: 150, x1: 200, seg: 0 }, bars[2], bars[3], bars[4]]); R.push({ name: 'split', times: r.times, knots: r.knots, notes: r.notes.map((n) => n.bar) });
  // the barline between bars 4 and 5 taken away: one bar, the moment 5 inside it at the place 420
  r = S.rebar(o, [bars[0], bars[1], bars[2], { x0: 320, x1: 520, seg: 1 }]); R.push({ name: 'merge', times: r.times, knots: r.knots, notes: r.notes.map((n) => n.bar) });
  // a line moved: the bars either side change, the others keep their times
  r = S.rebar(o, [bars[0], { x0: 100, x1: 180, seg: 0 }, { x0: 180, x1: 300, seg: 0 }, bars[3], bars[4]]); R.push({ name: 'move', times: r.times });
  return R; }"""
async def unit(b):
    ctx = await b.new_context(viewport={'width': 1180, 'height': 820}); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true;')
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    R = {x['name']: x for x in await pg.evaluate(UNIT)}
    check(R['same']['times'] == [1, 2, 3.5, 4, 5, 6] and R['same']['knots'][1] == [[0.3, 0.5]], f'the same bars: the same times and the same way through them {R["same"]}')
    t = R['split']['times']
    check(t[:2] == [1, 2] and abs(t[2] - 2.45) < 1e-6 and t[3:] == [3.5, 4, 5, 6], f'a bar split at a note heard: the new barline at the moment it was heard, the others kept {t}')
    check(R['split']['notes'] == [2, 4, 5], f'the notes go with the bar they are now in {R["split"]["notes"]}')
    t = R['merge']['times']; kn = R['merge']['knots']
    check(t == [1, 2, 3.5, 4, 6] and kn[3] and abs(kn[3][0][0] - 0.5) < 1e-3 and abs(kn[3][0][1] - 0.5) < 1e-3, f'a barline taken away: its moment stays inside the bar {t} {kn[3]}')
    t = R['move']['times']
    check(t[0] == 1 and t[1] == 2 and t[3:] == [4, 5, 6] and 2.45 < t[2] < 3.5, f'a line moved: only its moment changes {t}')
    await ctx.close()
VIEW = """() => { const box = document.querySelector('#stEraser'); const v = box.querySelector('.st-bars-view'); if (box.hidden || !v) return null;
  const r = v.getBoundingClientRect(), rm = box.querySelector('.st-bars-rm'), rr = rm.getBoundingClientRect(), f = box.querySelector('.st-bars-foot').getBoundingClientRect();
  const done = [...box.querySelectorAll('button')].find((b) => b.textContent === 'Done').getBoundingClientRect();
  return { v: [r.left, r.top, r.width, r.height], rm: rm.hidden ? null : [rr.left, rr.top, rr.right, rr.bottom], foot: f.bottom <= innerHeight + 1 && f.height > 0, done: done.top >= 0 && done.right <= innerWidth + 1,
    sideways: document.documentElement.scrollWidth > innerWidth + 1, count: box.querySelector('.st-bars-count').textContent }; }"""
async def run(b, name, vw, vh, phone):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, user_agent=UA if phone else None, device_scale_factor=2, has_touch=True); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true; window.__noTempo = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const S = await import('/js/studio.js'); const ST = S._studio; " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]')?.click(); await sleep(500);")
    if phone: await J("document.querySelector('#phoneTabs [data-tab=takes], .ph-tab[data-tab=takes]')?.click(); await sleep(400);")
    await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/clip.webm'); await pg.wait_for_timeout(4000)
    await J("document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
    opened = await J("return !!document.querySelector('#studio:not([hidden])') || !!ST.P")
    if not opened:
        check(False, f'{name}: Studio opened'); await ctx.close(); return
    await pg.evaluate(RENDER)
    r0 = await J("""const o = await S._addScoreFrom(window.__mmCanvas); o.times = o.times.map((t, k) => +(0.5 + k * 0.83 + (k % 3) * 0.04).toFixed(2)); o.synced = 'tap'; o.knots = o.layout.bars.map(() => []);
      window.__o = o; return { n: o.layout.bars.length, times: o.times.slice(), bars: o.layout.bars.map((b) => [Math.round(b.x0), Math.round(b.x1), b.seg]) };""")
    n0 = r0['n']
    # the button in the Score tab
    await J("document.querySelector('#stTabs [data-tab=score]')?.click(); await sleep(400);")
    has = await J("const b = [...document.querySelectorAll('.studio button')].find((x) => /^Edit the bars/.test(x.textContent)); if (!b) return false; b.scrollIntoView({ block: 'center' }); await sleep(200); b.click(); await sleep(900); return true;")
    check(has, f'{name}: Edit the bars, in the Score tab')
    v = await pg.evaluate(VIEW)
    check(v is not None, f'{name}: the bars open over Studio')
    if not v: await ctx.close(); return
    check(v['foot'] and v['done'] and not v['sideways'] and v['v'][3] > 80, f'{name}: it fits: the line, the count and Done on the screen {v}')
    check(v['count'] == f'{n0} bars', f'{name}: the number of bars shown ({v["count"]})')
    E = "const E = ST.barsEditor;"
    # a line: tap it (chosen), Remove on the screen, then removed
    ln = await J(E + "const ls = E.lines(); const j = ls[Math.min(2, ls.length - 1)]; const v = document.querySelector('.st-bars-view').getBoundingClientRect(); E.goTo && E.goTo(j); await sleep(50); return { j, x: E.bars[j].x1, sx: v.left + E.sx(E.bars[j].x1), y: v.top + v.height * 0.5 };")
    # (brought into view first: the line scrolled to the middle)
    async def tap(x, y):
        await pg.touchscreen.tap(x, y); await pg.wait_for_timeout(250)
    async def where(j):
        return await J(E + "const v = document.querySelector('.st-bars-view').getBoundingClientRect(); return { sx: v.left + E.sx(E.bars[a].x1), y: v.top + v.height * 0.5, left: v.left, right: v.right };", j)
    await J(E + "ST.barsEditor.center(a); await sleep(100);", ln['j'])
    w = await where(ln['j'])
    check(w['left'] < w['sx'] < w['right'], f'{name}: the line is on the screen {w}')
    await tap(w['sx'], w['y'])
    v = await pg.evaluate(VIEW)
    check(v['rm'] is not None and v['rm'][0] >= 0 and v['rm'][2] <= vw and v['rm'][1] >= 0, f'{name}: a line tapped: Remove shows over it, on the screen {v["rm"]}')
    if v['rm']:
        await tap((v['rm'][0] + v['rm'][2]) / 2, (v['rm'][1] + v['rm'][3]) / 2)
    c = await J(E + "return E.bars.length")
    check(c == n0 - 1, f'{name}: Remove: one bar fewer ({c})')
    v = await pg.evaluate(VIEW)
    check(v['count'] == f'{n0 - 1} bars (read: {n0})', f'{name}: the count says so ({v["count"]})')
    # a tap a little beside where it was: a barline again, on the one printed there
    w = await J(E + "const v = document.querySelector('.st-bars-view').getBoundingClientRect(); return { sx: v.left + E.sx(a[0]) + 7, y: v.top + v.height * 0.5 };", [ln['x']])
    await tap(w['sx'], w['y'])
    bs = await J(E + "return E.bars.map((b) => [b.x0, b.x1])")
    back = len(bs) == n0 and abs(bs[ln['j']][1] - ln['x']) < 2.5
    check(back, f'{name}: a tap beside the printed barline: a barline, on it ({len(bs)} bars, at {bs[ln["j"]][1] if len(bs) > ln["j"] else None:.1f} for {ln["x"]:.1f})')
    # dragged: moves with the finger (between its neighbours)
    j = ln['j']; w = await where(j)
    x0 = await J(E + "return E.bars[a].x1", j)
    await pg.evaluate("([x, y]) => { const v = document.querySelector('.st-bars-view'); const ev = (t, cx) => v.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, pointerId: 31, pointerType: 'touch', isPrimary: true, clientX: cx, clientY: y, buttons: t === 'pointerup' ? 0 : 1 })); ev('pointerdown', x); for (let i = 1; i <= 8; i++) ev('pointermove', x - i * 3); ev('pointerup', x - 24); }", [w['sx'], w['y']])
    await pg.wait_for_timeout(200)
    x1 = await J(E + "return E.bars[a].x1", j)
    check(x1 < x0 - 1, f'{name}: a line dragged moves ({x0:.1f} -> {x1:.1f})')
    # Undo: back where it was
    await J("[...document.querySelectorAll('#stEraser .icon-btn')].find((b) => b.getAttribute('aria-label') === 'Undo').click(); await sleep(150);")
    x2 = await J(E + "return E.bars[a].x1", j)
    check(abs(x2 - x0) < 0.01, f'{name}: Undo puts it back ({x2:.1f})')
    # a new barline in the middle of a bar with no barline printed there: one more bar
    mid = await J(E + "const k = E.bars.findIndex((b) => b.x1 - b.x0 > 60); const b = E.bars[k]; ST.barsEditor.center(k); await sleep(60); const v = document.querySelector('.st-bars-view').getBoundingClientRect(); return { k, x: (b.x0 + b.x1) / 2, sx: v.left + E.sx((b.x0 + b.x1) / 2), y: v.top + v.height * 0.5 };")
    await tap(mid['sx'], mid['y'])
    c = await J(E + "return E.bars.length")
    check(c == n0 + 1, f'{name}: a tap in a bar: a barline there, one bar more ({c})')
    # Done: the bars taken in, the times of the bars left as they were kept
    await J("[...document.querySelectorAll('#stEraser button')].find((b) => b.textContent === 'Done').click(); await sleep(600);")
    r1 = await J("const o = window.__o; return { n: o.layout.bars.length, times: o.times.slice(), bars: o.layout.bars.map((b) => [Math.round(b.x0), Math.round(b.x1), b.seg]), hidden: document.querySelector('#stEraser').hidden, read: !!o.layout.bars0, toast: document.querySelector('.toast')?.textContent || '' };")
    check(r1['hidden'] and r1['n'] == n0 + 1, f'{name}: Done: the line has {n0 + 1} bars now ({r1["n"]})')
    k = mid['k']
    kept = all(abs(r1['times'][i] - r0['times'][i]) < 1e-9 for i in range(k + 1)) and all(abs(r1['times'][i + 1] - r0['times'][i]) < 1e-9 for i in range(k + 1, n0 + 1))
    check(kept, f'{name}: every bar left as it was keeps its time to the hundredth')
    check(r0['times'][k] < r1['times'][k + 1] < r0['times'][k + 1], f'{name}: the new barline: between the times of the bar it was put in ({r0["times"][k]} < {r1["times"][k + 1]:.2f} < {r0["times"][k + 1]})')
    # opened again: Back to as read, Done: as it was read, the times as they were
    await J("const b = [...document.querySelectorAll('.studio button')].find((x) => /^Edit the bars/.test(x.textContent)); b.click(); await sleep(800);")
    await J("[...document.querySelectorAll('#stEraser button')].find((b) => b.textContent === 'Back to as read').click(); await sleep(150); [...document.querySelectorAll('#stEraser button')].find((b) => b.textContent === 'Done').click(); await sleep(500);")
    r2 = await J("const o = window.__o; return { n: o.layout.bars.length, times: o.times.slice(), bars: o.layout.bars.map((b) => [Math.round(b.x0), Math.round(b.x1), b.seg]) };")
    check(r2['bars'] == r0['bars'] and all(abs(a - c) < 1e-9 for a, c in zip(r2['times'], r0['times'])), f'{name}: Back to as read: the bars and their times as at first')
    # Cancel changes nothing
    await J("const b = [...document.querySelectorAll('.studio button')].find((x) => /^Edit the bars/.test(x.textContent)); b.click(); await sleep(800); ST.barsEditor.removeLine(ST.barsEditor.lines()[0]); [...document.querySelectorAll('#stEraser button')].find((b) => b.textContent === 'Cancel').click(); await sleep(300);")
    r3 = await J("return window.__o.layout.bars.length")
    check(r3 == n0, f'{name}: Cancel: nothing changed ({r3})')
    if os.environ.get('SHOT'):
        await J("const b = [...document.querySelectorAll('.studio button')].find((x) => /^Edit the bars/.test(x.textContent)); b.click(); await sleep(800); const E = ST.barsEditor; const j = E.lines()[1]; E.center(j); E.choose(j); await sleep(200);")
        await pg.screenshot(path=f'/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/bars_{name}.png')
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    if BR != 'chromium': print('(Studio needs a video brought in: Chromium)'); print('FAILS 0'); return
    async with async_playwright() as p:
        b = await getattr(p, BR).launch(args=['--autoplay-policy=no-user-gesture-required'])
        await unit(b)
        for d in [('ipad-land', 1180, 820, False), ('ipad-portrait', 820, 1180, False), ('ipad-mini', 744, 1133, False), ('ipad-pro13', 1376, 1032, False),
                  ('iphone', 393, 852, True), ('iphone-land', 852, 393, True)]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
