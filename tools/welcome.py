# The first launch: a calm welcome in three pages (hello, what Stand does, your instrument), as on a
# new iPhone. On every iPad and iPhone, both ways round, light and dark: each page fits (nothing cut,
# nothing sideways), the button is on the screen and reachable, Back and a swipe move between pages,
# the instrument chosen sets its tools, the tools open to change them, Start leads into the tour
# (without saying hello twice), and on the iPhone the same welcome comes first, then its tour.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
FIT = """() => { const w = document.querySelector('#welcome'); const p = w.querySelector('.wel-page.on'); const btn = [...w.querySelectorAll('.wel-next')].find((b) => !b.hidden);
  const r = btn.getBoundingClientRect(), pr = p.getBoundingClientRect();
  const kids = [...p.children].filter((k) => k.offsetParent !== null).map((k) => k.getBoundingClientRect());
  const top = Math.min(...kids.map((k) => k.top)), bot = Math.max(...kids.map((k) => k.bottom));
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { step: +w.dataset.step, btnIn: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth, btnHit: !!hit && btn.contains(hit),
    sideways: document.documentElement.scrollWidth > innerWidth + 1 || p.scrollWidth > p.clientWidth + 1,
    // the page's content either fits or can be scrolled to (never cut off at the top)
    fits: p.scrollHeight <= p.clientHeight + 1, topOk: top >= pr.top - 1 || p.scrollTop > 0 || p.scrollHeight > p.clientHeight, cutTop: top < pr.top - 1 && p.scrollTop === 0,
    over: bot > pr.bottom + 1 && p.scrollHeight <= p.clientHeight + 1, h: Math.round(pr.height) }; }"""
async def run(b, name, vw, vh, phone, dark=False, reduce=False):
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, user_agent=UA if phone else None, device_scale_factor=2, has_touch=True,
                              color_scheme='dark' if dark else 'light', reduced_motion='reduce' if reduce else 'no-preference')
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    tag = name + (' dark' if dark else '') + (' reduce motion' if reduce else '')
    J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
    shown = await J("return !document.querySelector('#welcome').hidden && !document.querySelector('.tour')")
    check(shown, f'{tag}: the welcome comes first (no tour over it)')
    if not shown: await ctx.close(); return
    for i in range(3):
        if i == 2: await J("document.querySelector('#welToolsBtn').click(); await sleep(300);")
        f = await pg.evaluate(FIT)
        check(f['step'] == i, f'{tag}: page {i + 1} of 3')
        check(f['btnIn'] and f['btnHit'], f'{tag}: page {i + 1}: its button on the screen and nothing over it')
        check(not f['sideways'], f'{tag}: page {i + 1}: nothing goes off to the side')
        check(not f['cutTop'] and not f['over'], f'{tag}: page {i + 1}: the words fit or scroll, never cut {f}')
        if i == 0:
            vis = await J("const r = document.querySelector('#welRestore').getBoundingClientRect(); return r.bottom <= innerHeight && r.width > 0;")
            check(vis, f'{tag}: Bring back a backup is there on the first page')
            pc = await J("return [...document.querySelectorAll('#welFeats li')].filter((l) => l.offsetParent).map((l) => l.dataset.for)")
        if i < 2: await J("document.querySelector('#welNext').click(); await sleep(650);")
    check(len(pc) == 3 and all(x == ('phone' if phone else 'ipad') for x in pc), f'{tag}: what Stand does, told for this device {pc}')
    # Back, then a swipe forward
    await J("document.querySelector('#welBack').click(); await sleep(600);")
    st = await J("return +document.querySelector('#welcome').dataset.step")
    check(st == 1, f'{tag}: Back goes one page back ({st})')
    cdp = await ctx.new_cdp_session(pg) if BR == 'chromium' else None
    if cdp:
        y = vh * 0.45
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': vw * 0.8, 'y': y, 'id': 1}]})
        for k in range(1, 9): await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': vw * 0.8 - vw * 0.5 * k / 8, 'y': y, 'id': 1}]}); await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(600)
        st = await J("return +document.querySelector('#welcome').dataset.step")
        check(st == 2, f'{tag}: a swipe to the left goes on ({st})')
    else: await J("document.querySelector('#welNext').click(); await sleep(600);")
    # the instrument sets the tools (until they are changed by hand)
    r = await J("""const s = document.querySelector('#welInst'); const a = document.querySelector('#welToolsSum').textContent;
      s.value = 'piano'; s.dispatchEvent(new Event('change')); await sleep(100); const b = document.querySelector('#welToolsSum').textContent;
      const chips = [...document.querySelectorAll('#welTools button.on')].map((x) => x.textContent); return { a, b, chips, empty: s.classList.contains('empty') };""")
    check(r['b'] and not r['empty'], f'{tag}: choosing piano: its tools shown in one short line {r}')
    await J("document.querySelector('#welGo').click(); await sleep(1200);")
    t = await J("const c = document.querySelector('.tour-card'); return { gone: document.querySelector('#welcome').hidden, tour: !!c, title: c ? c.querySelector('h2,h3,strong,b,.tour-title')?.textContent || c.textContent.slice(0, 40) : '' };")
    check(t['gone'] and t['tour'], f'{tag}: Start: the welcome goes and the tour shows Stand around {t}')
    check('Welcome' not in t['title'] and 'Stand on your iPhone' not in t['title'], f'{tag}: the tour does not say hello again ({t["title"]})')
    s = await J("const { db } = await import('/js/db.js'); return null;")
    await J("document.querySelector('.tour-skip')?.click(); await sleep(400);")
    await pg.reload(); await pg.wait_for_timeout(1800)
    again = await J("return { wel: !document.querySelector('#welcome').hidden, tour: !!document.querySelector('.tour') }")
    check(not again['wel'] and not again['tour'], f'{tag}: opened again: straight to Stand {again}')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await ctx.close()
async def restore(b):
    ctx = await b.new_context(viewport={'width': 1180, 'height': 820}); pg = await ctx.new_page()
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    await pg.evaluate("document.querySelector('#welRestore').click()"); await pg.wait_for_timeout(800)
    r = await pg.evaluate("({ wel: document.querySelector('#welcome').hidden, bk: !document.querySelector('#panel-backup')?.hidden })")
    check(r['wel'] and r['bk'], f'Bring back a backup: the welcome goes, Backup opens {r}')
    await pg.keyboard.press('Escape'); await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        D = [('ipad-land', 1180, 820, False), ('ipad-portrait', 820, 1180, False), ('ipad-mini', 744, 1133, False), ('ipad-mini-land', 1133, 744, False),
             ('ipad-pro13', 1376, 1032, False), ('ipad-pro13-portrait', 1032, 1376, False), ('ipad-pro11', 1210, 834, False),
             ('iphone', 393, 852, True), ('iphone-land', 852, 393, True), ('iphone-se', 375, 667, True), ('iphone-se-land', 667, 375, True), ('iphone-max', 440, 956, True)]
        for d in D: await run(b, *d)
        await run(b, 'ipad-land', 1180, 820, False, dark=True); await run(b, 'iphone', 393, 852, True, dark=True)
        await run(b, 'ipad-portrait', 820, 1180, False, reduce=True)
        await restore(b)
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
