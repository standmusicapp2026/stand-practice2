# The sample score from the empty library, with the iPad's storage slow (every save held 3 s, as on a
# new iPad's first minute): the tap is answered at once ("Opening the sample score…", in the language
# of the iPad), the score opens, the message goes away, a second tap meanwhile adds no second copy;
# and quickly with normal storage, in English, with no message left behind; no errors.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
async def run(p, lang, slow, check):
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
    pg = await ctx.new_page()
    await pg.add_init_script(f"window.__noTour = true; try {{ localStorage.setItem('standLang', '{lang}'); }} catch {{}}")
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
    await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove()); document.querySelector('.tour-skip')?.click();")
    if slow:
        await J("const { db } = await import('/js/db.js'); const put = db.put; db.put = async (s, v) => { await sleep(3000); return put(s, v); }; window.__slowDb = true;")
    vis = await J("const b = document.querySelector('#sampleBtn'); return !!(b && b.offsetParent);")
    check(vis, f'{lang}: the sample button is on the empty library')
    if not vis:
        await b.close(); return
    r = await J("""const b = document.querySelector('#sampleBtn'); const t0 = performance.now(); b.click(); await sleep(150); b.click();
      let msg = '', at = 0;
      while (performance.now() - t0 < 2500) { const t = document.querySelector('#toast'); if (!t.hidden && t.textContent) { msg = t.textContent; at = Math.round(performance.now() - t0); break; } await sleep(50); }
      let open = 0; while (performance.now() - t0 < 40000) { const cs = [...document.querySelectorAll('#stage canvas.art')]; if (!document.querySelector('#score').hidden && cs.length && cs.every((c) => c.width > 10)) { open = Math.round(performance.now() - t0); break; } await sleep(100); }
      await sleep(600); const t = document.querySelector('#toast');
      const { db } = await import('/js/db.js'); const n = (await db.all('scores')).filter((s) => /Cello Suite No\\. 3/.test(s.title)).length;
      return { msg, at, open, after: t.hidden ? '' : t.textContent, n, disabled: document.querySelector('#sampleBtn').disabled };""")
    if slow:
        want = {'pt-PT': 'A abrir a partitura de exemplo…', 'en': 'Opening the sample score…'}[lang]
        check(r['msg'] == want and r['at'] < 1500, f"{lang}: the tap is answered at once: \"{r['msg']}\" after {r['at']} ms")
    else:
        check(r['msg'] == '', f"{lang}: quick, so no message at all ({r['msg']!r})")
    check(r['open'] > 0, f"{lang}: the score opens ({r['open']} ms)")
    check(r['after'] == '', f"{lang}: no message left once it is open ({r['after']!r})")
    check(r['n'] == 1, f"{lang}: one copy of the sample, though tapped twice ({r['n']})")
    check(not r['disabled'], f"{lang}: the button works again afterwards")
    check(not errs, f'{lang}: no errors {errs[:2]}')
    await b.close()
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        await run(p, 'pt-PT', True, check)
        await run(p, 'en', False, check)
    print('\n' + ('ALL OK' if not fails else f'{len(fails)} FAILED'))
asyncio.run(main())
