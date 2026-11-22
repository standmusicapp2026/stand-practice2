# Studio: a score chosen is looked over first, on one screen: its bars (each with its number, put
# right by hand) and Clean (what is wiped from the line), a switch between them at the top. Done: the
# Studio goes on with it (follows the playing, with the bars as left), and these are no longer
# offered in its tabs (to look again, the score is chosen again). Every iPad and iPhone, both ways round.
import asyncio, os, sys, base64
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); SHOT = os.environ.get('SHOT'); SP = os.environ.get('SP', '/tmp'); BR = os.environ.get('BR', 'chromium')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def run(b, name, vp, mob):
    ctx = await b.new_context(viewport=vp, device_scale_factor=2, has_touch=True, is_mobile=mob and BR == 'chromium'); pg = await ctx.new_page()
    await pg.add_init_script('window.__noTour = true;')
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
    J = lambda js, a=None: pg.evaluate("async (A) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const S = await import('/js/studio.js'); const ST = S._studio; " + js + " }", a)
    await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]').click(); await sleep(500);")
    await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/clip.webm'); await pg.wait_for_timeout(4000)
    await J("document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
    img = base64.b64encode(open('/home/claude/tc/raw-002.jpg', 'rb').read()).decode()
    # the picker answered by the test: these lines chosen
    await J("""const img = new Image(); img.src = 'data:image/jpeg;base64,' + A; await img.decode();
      const c = document.createElement('canvas'); c.width = 2080; c.height = 620; c.getContext('2d').drawImage(img, -150, -500);
      globalThis.__studioPick = async () => ({ canvas: c, source: { title: 'Test' }, page: 0, box: null });
      S._addScore(); for (let i = 0; i < 80; i++) { await sleep(200); if (!document.querySelector('#stEraser').hidden && document.querySelector('#stEraser .st-bars-view')) break; }""", img)
    UI = """const box = document.querySelector('#stEraser'), top = box.querySelector('.st-er-top'); const sw = top && top.querySelector('.seg'); const done = [...top.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Done');
      const inV = (e) => { if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth + 0.5 && r.top >= 0 && r.bottom <= innerHeight + 0.5; };
      const hit = (e) => { const r = e.getBoundingClientRect(); const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!h && e.contains(h); };
      const lead = box.querySelector('.st-review-lead');
      return { open: !box.hidden, bars: !!box.querySelector('.st-bars-view'), clean: !!box.querySelector('.st-er-tools .seg'), sw: !!sw && [...sw.querySelectorAll('button')].map((b) => b.textContent.trim()), swOk: !!sw && inV(sw) && [...sw.querySelectorAll('button')].every(hit),
        doneOk: !!done && inV(done) && hit(done), cancel: [...top.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Cancel' && !b.hidden), lead: !!lead && inV(lead), side: document.documentElement.scrollWidth > innerWidth + 1 };"""
    u = await J(UI)
    check(u['open'] and u['bars'], f'{name}: a score chosen: looked over first, on its bars {u}')
    check(u['sw'] == ['Bars', 'Clean'] and u['swOk'], f'{name}: Bars | Clean at the top, on the screen, nothing over them')
    check(u['doneOk'] and not u['cancel'] and u['lead'] and not u['side'], f'{name}: Done reachable, a word on what to do, nothing off to the side')
    if SHOT: await pg.screenshot(path=f'{SP}/review_{name}_bars.png')
    # to Clean: the eraser on the same line; a wipe
    await J("[...document.querySelectorAll('#stEraser .st-er-top .seg button')].find((b) => b.textContent.trim() === 'Clean').click(); await sleep(1500);")
    u = await J(UI)
    check(u['open'] and u['clean'] and not u['bars'] and u['sw'] == ['Bars', 'Clean'] and u['doneOk'], f'{name}: Clean: the same line, to wipe away what should not show {u}')
    if SHOT: await pg.screenshot(path=f'{SP}/review_{name}_clean.png')
    await J("""const v = document.querySelector('#stEraser .st-er-view'), r = v.getBoundingClientRect(); const t = v.querySelector('canvas') || v;
      const ev = (ty, x) => t.dispatchEvent(new PointerEvent(ty, { bubbles: true, cancelable: true, pointerId: 9, pointerType: 'touch', isPrimary: true, clientX: x, clientY: r.top + r.height * 0.5, buttons: ty === 'pointerup' ? 0 : 1 }));
      ev('pointerdown', r.left + r.width * 0.3); for (let i = 1; i <= 8; i++) { ev('pointermove', r.left + r.width * (0.3 + i * 0.01)); await sleep(16); } ev('pointerup', r.left + r.width * 0.38); await sleep(300);""")
    # back to Bars: one barline added
    await J("[...document.querySelectorAll('#stEraser .st-er-top .seg button')].find((b) => b.textContent.trim() === 'Bars').click(); await sleep(1500);")
    n0 = await J("const o = ST.P.overlays.find((x) => x.kind === 'score'); return { n: o.layout.bars.length, erase: (o.erase || []).length, ed: !!ST.barsEditor };")
    check(n0['erase'] >= 1 and n0['ed'], f'{name}: back to Bars, what was wiped is kept {n0}')
    r = await J("""const E = ST.barsEditor; const b = E.bars[Math.floor(E.bars.length / 2)]; const x = (b.x0 + b.x1) / 2; const before = E.bars.length; E.addAt(x, b.seg, true); await sleep(100);
      return { before, after: E.bars.length };""")
    await J("[...document.querySelectorAll('#stEraser .st-er-top button')].find((b) => b.textContent.trim() === 'Done').click(); await sleep(2500); for (let i = 0; i < 60 && !document.querySelector('#stBusy').hidden; i++) await sleep(300);")
    f = await J("""const o = ST.P.overlays.find((x) => x.kind === 'score'); ST.tab = 'score'; ST.sel = { id: o.id }; document.querySelector('#stTabScore, [data-tab=score]')?.click(); await sleep(300);
      const side = document.querySelector('#stSide').textContent; document.querySelector('[data-tab=timing]')?.click(); await sleep(300); const side2 = document.querySelector('#stSide').textContent;
      return { closed: document.querySelector('#stEraser').hidden, reviewed: !!o.reviewed, bars: o.layout.bars.length, erase: (o.erase || []).length, times: !!o.times, editBars: /Edit the bars/.test(side) || /Edit the bars/.test(side2), editShown: /Edit what is shown/.test(side), again: /Choose the score again/.test(side) };""")
    check(f['closed'] and f['reviewed'] and f['bars'] == r['after'] and f['erase'] >= 1, f'{name}: Done: the Studio goes on with the line as left ({r["before"]} -> {f["bars"]} bars, wiped kept) {f}')
    check(f['times'], f'{name}: then followed / timed')
    check(not f['editBars'] and not f['editShown'] and f['again'], f'{name}: no longer offered in the tabs; "Choose the score again" instead')
    check(not errs, f'{name}: no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch(args=['--autoplay-policy=no-user-gesture-required'] if BR == 'chromium' else [])
        for d in [('ipad-land', {'width': 1180, 'height': 820}, False), ('ipad-portrait', {'width': 820, 'height': 1180}, False), ('ipad-mini', {'width': 744, 'height': 1133}, False),
                  ('ipad-pro13', {'width': 1376, 'height': 1032}, False), ('iphone', {'width': 393, 'height': 852}, True), ('iphone-land', {'width': 852, 'height': 393}, True),
                  ('iphone-se', {'width': 375, 'height': 667}, True)][:int(os.environ.get('ND', '7'))]:
            await run(b, *d)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
