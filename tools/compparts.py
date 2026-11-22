# Compose: write one part on its own (the clarinet alone, as its player reads it: its written key, its
# own pages), then another; the full score has everything, in the right staves, at the right pitch.
# The choice is beside the title, remembered for each composition, and safe when a part is removed.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
SHOT = os.environ.get('SHOT', '')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
PRE = "const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const L = await import('/js/compose/engrave.js'); const C = window.__compose; "
# where on the screen a note at step p (from the staff's bottom line) of bar m, beat b goes
WHERE = """const [pi, si, m, b, p] = a; const lay = C.lay; for (let i = 0; i < lay.pages.length; i++) for (const sy of lay.pages[i].systems) { const ms = sy.measures.find((q) => q.m === m); if (!ms) continue;
  const s = sy.staves.find((q) => q.pi === pi && q.si === si); if (!s) continue; const pgEl = C.pages[i].pg, r = pgEl.getBoundingClientRect(), k = r.width / lay.W;
  pgEl.scrollIntoView({ block: 'center' }); await sleep(250); const r2 = pgEl.getBoundingClientRect();
  const x = ms.x0 + (ms.x1 - ms.x0) * (0.18 + b * 0.2), y = s.y + 4 - p / 2; return [r2.left + x * k, r2.top + y * k]; } return null;"""

async def run(b, name, vw, vh, phone=False):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, has_touch=True, device_scale_factor=2, is_mobile=phone and BR == 'chromium')
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
    J = lambda js, a=None: pg.evaluate("async (a) => { " + PRE + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
    await J("await E.createComposition({ title: 'Parts', insts: ['clarinet', 'violin', 'cello'], time: [4, 4], bars: 16, key: 0 }); await sleep(900); C.tool.dur = 4; C.tool.dots = 0; C.tool.rest = false; C.tool.acc = null;")
    r = await J("const s = document.querySelector('#cpView'); const r = s.getBoundingClientRect(); return { shown: !s.hidden && r.width > 40, onBar: r.top >= 0 && r.bottom <= 80 && r.right <= innerWidth, opts: [...s.options].map((o) => o.textContent), v: s.value };")
    check(r['shown'] and r['onBar'] and r['opts'] == ['Full score', 'Clarinet in B♭', 'Violin', 'Violoncello'] and r['v'] == '', f'{name}: beside the title: the full score, or one part {r}')
    full_pages = await J("return C.lay.pages.length")
    async def choose(v):
        await J("const s = document.querySelector('#cpView'); s.value = a; s.dispatchEvent(new Event('change')); await sleep(500);", v)
    clar = await J("return C.score.parts[0].id")
    await choose(clar)
    r = await J("const lay = C.lay; const pis = new Set(); for (const pgx of lay.pages) for (const sy of pgx.systems) for (const s of sy.staves) pis.add(s.pi); return { pis: [...pis], concert: lay.concert, on: document.querySelector('#cpView').classList.contains('on'), hint: !document.querySelector('#cpHint').hidden && document.querySelector('#cpHint').textContent };")
    check(r['pis'] == [0] and r['concert'] is False and r['on'], f'{name}: the clarinet alone, in its written key {r["pis"]} {r["concert"]}')
    check(bool(r['hint']) and 'full score' in r['hint'], f'{name}: says so: what is written here is in the full score too ({r["hint"]})')
    if SHOT: await pg.screenshot(path=f'{SHOT}/cp_part_{name}.png')
    # written with the pen (the mouse here): G4 on the clarinet's second line, bar 1, beat 1
    async def write(pi, m, beat, p):
        xy = await J(WHERE, [pi, 0, m, beat, p])
        if not xy: return False
        await pg.mouse.move(xy[0], xy[1]); await pg.wait_for_timeout(60); await pg.mouse.down(); await pg.mouse.up(); await pg.wait_for_timeout(250)
        return True
    ok = await write(0, 0, 0, 2) and await write(0, 0, 1, 4)
    r = await J("const ev = C.score.parts[0].staves[0].bars[0].filter((e) => e.notes); const inst = M.instAt(C.score.parts[0], 0); return ev.map((e) => ({ c: [e.notes[0].s, e.notes[0].a], w: (() => { const w = M.toWritten(e.notes[0], inst); return [w.s, w.a]; })() }));")
    # treble clef: bottom line E4; step 2 = G4, step 4 = B4. Written G4 and B4 (in D major, both natural)
    # sound F4 and A4: the model keeps the sounding pitch
    E4 = await J("return M.CLEFS.treble.bottom")
    check(ok and len(r) == 2 and r[0]['w'] == [E4 + 2, 0] and r[1]['w'] == [E4 + 4, 0] and r[0]['c'] == [E4 + 1, 0] and r[1]['c'] == [E4 + 3, 0], f'{name}: written in the part as read (G, B), kept as they sound (F, A) {r}')
    # the violin on its own, then a note there too
    vio = await J("return C.score.parts[1].id")
    await choose(vio)
    r = await J("const pis = new Set(); for (const pgx of C.lay.pages) for (const sy of pgx.systems) for (const s of sy.staves) pis.add(s.pi); return [...pis];")
    check(r == [1], f'{name}: then the violin alone {r}')
    await write(1, 0, 0, 2)
    r = await J("return C.score.parts[1].staves[0].bars[0].filter((e) => e.notes).map((e) => [e.notes[0].s, e.notes[0].a]);")
    check(r == [[E4 + 2, 0]], f'{name}: the violin\'s G is G {r}')
    # undo, in a part: the last note goes, the view stays
    await J("document.querySelector('#cpPalUndo').click(); await sleep(300);")
    r = await J("return [C.score.parts[1].staves[0].bars[0].filter((e) => e.notes).length, document.querySelector('#cpView').value === C.score.parts[1].id];")
    check(r == [0, True], f'{name}: undo takes it back, the violin still shown {r}')
    await J("document.querySelector('#cpPalRedo').click(); await sleep(300);")
    # back to the full score: everything is there, in its place
    await choose('')
    r = await J("""const pis = new Set(); for (const pgx of C.lay.pages) for (const sy of pgx.systems) for (const s of sy.staves) pis.add(s.pi);
      const n = C.score.parts.map((p) => p.staves[0].bars[0].filter((e) => e.notes).length); return { pis: [...pis].sort(), n, pages: C.lay.pages.length, on: document.querySelector('#cpView').classList.contains('on') };""")
    check(r['pis'] == [0, 1, 2] and r['n'] == [2, 1, 0] and r['pages'] == full_pages and not r['on'], f'{name}: the full score has it all, in the right staves {r}')
    # the full score's drawing shows the clarinet's notes where they belong (concert pitch: F and A)
    r = await J("""const c = document.createElement('canvas'); const lay = C.lay; c.width = lay.W * 3; c.height = lay.H * 3; const g = c.getContext('2d'); g.scale(3, 3); const hit = L.drawPage(g, lay, 0);
      const e = hit.events.filter((x) => !x.rest && x.m === 0); return e.map((x) => [x.staff, +(x.notes[0].y - x.y).toFixed(2)]);""")
    check(len(r) == 3, f'{name}: drawn in the full score {r}')
    # remembered for this composition
    await choose(clar)
    r = await J("const id = C.id; await E.openComposition(id); await sleep(600); return [document.querySelector('#cpView').value === C.score.parts[0].id, C.lay.partIndex];")
    check(r == [True, 0], f'{name}: opened again, still the clarinet part {r}')
    # played while a part is shown: no trouble
    await J("document.querySelector('#cpPlay').click(); await sleep(1200); document.querySelector('#cpPlay').click(); await sleep(300);")
    # its part removed: back to the full score
    r = await J("""const M2 = M; E; const id0 = C.score.parts[0].id; const before = C.score.parts.length;
      window.__composeTest && 0; const pnl = document.querySelector('[data-panel=\"cpinst\"]'); pnl.click(); await sleep(400);
      const del = document.querySelector('#cpParts li button[aria-label^=\"Remove\"]'); del.click(); await sleep(100); del.click(); await sleep(500);
      document.querySelector('#panel-cpinst [data-close], .panel:not([hidden]) [data-close]')?.click(); await sleep(300);
      return { parts: C.score.parts.length, before, view: document.querySelector('#cpView').value, idx: C.lay.partIndex === undefined, opts: [...document.querySelector('#cpView').options].map((o) => o.textContent) };""")
    check(r['parts'] == 2 and r['view'] == '' and r['idx'] and r['opts'] == ['Full score', 'Violin', 'Violoncello'], f'{name}: the part shown removed: back to the full score {r}')
    # one instrument only: no choice to make
    await J("await E.createComposition({ title: 'Solo', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(800);")
    r = await J("return document.querySelector('#cpView').hidden")
    check(r, f'{name}: a piece for one instrument: nothing to choose')
    check(not errs, f'{name}: no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        for d in [('ipad-land', 1180, 820), ('ipad-portrait', 820, 1180), ('ipad-pro13', 1376, 1032), ('ipad-mini', 744, 1133)]:
            await run(b, *d)
        await run(b, 'iphone', 390, 844, phone=True)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
