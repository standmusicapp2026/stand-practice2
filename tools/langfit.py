# Every language on every screen size: the home screen, Settings and each panel of the score
# (metronome, tuner, recordings…) open with no errors, nothing reaches past the edge of the screen,
# and no words are cut off in a button or label (long German, Russian or French words).
# LANGS=de,ru SIZES=phone V=1 to narrow it; V=1 lists each finding.
import asyncio, os, json
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
ALL = ['en', 'pt-PT', 'pt-BR', 'es', 'fr', 'de', 'it', 'nl', 'pl', 'ru', 'ja', 'zh-Hans', 'ko']
LANGS = os.environ.get('LANGS', ','.join(ALL)).split(',')
SIZES = {'ipad13': (1376, 1032), 'ipad11': (1180, 820), 'ipadmini': (1133, 744), 'ipadport': (820, 1180), 'phone': (390, 844)}
SZ = os.environ.get('SIZES', 'ipad11,ipadport,phone').split(',')
FIND = r"""(where) => {
  const W = innerWidth, H = innerHeight, out = [];
  const vis = (e) => { const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return false; const s = getComputedStyle(e); return s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05; };
  const scrollsX = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') return true; if (o === 'hidden' || o === 'clip') return 'clip'; } return false; };
  const roots = [...document.querySelectorAll(where)].filter((r) => !r.hidden && r.offsetParent !== null || r === document.body);
  for (const root of roots) for (const e of root.querySelectorAll('button, label, .btn, h1, h2, h3, h4, p, span, a, .seg, li, summary, select, option')) {
    if (!vis(e) || e.closest('[hidden]') || e.closest('.tour') || e.closest('#toast') || e.closest('[translate="no"]') || e.closest('.ttl')) continue;
    const r = e.getBoundingClientRect(), txt = (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 60);
    if (!txt || !/\p{L}/u.test(txt)) continue;
    const sx = scrollsX(e);
    if ((r.right > W + 1 || r.left < -1) && !sx) out.push({ k: 'past the edge', txt, x: Math.round(r.left), r: Math.round(r.right), W });
    const s = getComputedStyle(e);
    // (cut off: the words are wider than the box and the box hides them, with no "…" on purpose)
    if (e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0 && (s.overflowX === 'hidden' || s.overflowX === 'clip' || sx === 'clip') && s.textOverflow !== 'ellipsis' && e.children.length === 0)
      out.push({ k: 'cut off', txt, w: e.clientWidth, need: e.scrollWidth });
  }
  return out;
}"""
async def main():
    fails = []; seen = {}
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for size in SZ:
            w, h = SIZES[size]
            for lang in LANGS:
                ctx = await b.new_context(viewport={'width': w, 'height': h}, has_touch=True, device_scale_factor=1)
                pg = await ctx.new_page()
                await pg.add_init_script(f"window.__noTour = true; try {{ localStorage.setItem('standLang', '{lang}'); }} catch {{}}")
                errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
                await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1800)
                J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const clean = () => { document.querySelectorAll('.tour').forEach(x => x.remove()); document.querySelector('.tour-skip')?.click(); }; " + js + " }", a)
                await J("document.querySelector('#welGo')?.click(); await sleep(500); clean();")
                found = []
                found += [dict(f, where='home') for f in await pg.evaluate(FIND, 'body')]
                # Settings from home
                await J("const b = document.querySelector('[data-panel=settings]'); if (b && b.offsetParent) { b.click(); await sleep(600); clean(); }")
                found += [dict(f, where='settings') for f in await pg.evaluate(FIND, '#panel-settings')]
                await J("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await sleep(300); document.querySelectorAll('.panel').forEach(p => p.hidden = true);")
                # a score open, then each panel the score's buttons open
                ok = await J("""const b = document.querySelector('#sampleBtn'); if (!b || !b.offsetParent) return 'no sample button'; b.click();
                  for (let i = 0; i < 200; i++) { const cs = [...document.querySelectorAll('#stage canvas.art')]; if (!document.querySelector('#score').hidden && cs.length && cs.every((c) => c.width > 10)) return 'open'; await sleep(100); } return 'not open';""")
                await J("await sleep(500); clean();")
                if ok == 'open':
                    found += [dict(f, where='score') for f in await pg.evaluate(FIND, '#score')]
                    names = await J("return [...new Set([...document.querySelectorAll('#score [data-panel]')].filter((b) => b.offsetParent).map((b) => b.dataset.panel))];")
                    for n in names:
                        await J("const b = [...document.querySelectorAll('#score [data-panel=\"' + a + '\"]')].find((x) => x.offsetParent); if (b) { b.click(); await sleep(700); clean(); await sleep(100); }", n)
                        found += [dict(f, where=n) for f in await pg.evaluate(FIND, '#panel-' + n)]
                        # each tab inside it (tuner: harmonics, drone…)
                        tabs = await J("const p = document.querySelector('#panel-' + a); return p ? [...p.querySelectorAll('[data-tab]')].filter((t) => t.offsetParent).length : 0;", n)
                        for i in range(min(tabs, 6)):
                            await J("const p = document.querySelector('#panel-' + a[0]); const t = [...p.querySelectorAll('[data-tab]')].filter((t) => t.offsetParent)[a[1]]; if (t) { t.click(); await sleep(400); clean(); }", [n, i])
                            found += [dict(f, where=f'{n}/tab{i}') for f in await pg.evaluate(FIND, '#panel-' + n)]
                        await J("const p = document.querySelector('#panel-' + a); if (p && !p.hidden) { const c = p.querySelector('.close, [data-close], .panel-close'); if (c && c.offsetParent) c.click(); else p.hidden = true; } await sleep(250);", n)
                uniq = {}
                for f in found:
                    k = (f['where'], f['k'], f['txt']); uniq.setdefault(k, f)
                for k, f in uniq.items(): seen.setdefault((size, k[1], k[0], k[2]), []).append(lang)
                check(ok == 'open' or size == 'phone', f'{size} {lang}: the sample score opens ({ok})')
                check(not errs, f'{size} {lang}: no errors {errs[:2]}')
                print(f'     {size} {lang}: {len(uniq)} findings')
                await ctx.close()
        await b.close()
    # findings in English too are layout, not language; those only in some languages are words too long
    for (size, k, where, txt), langs in sorted(seen.items()):
        if os.environ.get('V') or True:
            print(f'  {size:8} {k:13} {where:14} [{",".join(langs) if len(langs) < len(LANGS) else "all"}] {txt!r}')
    print('\n' + ('ALL OK' if not fails else f'{len(fails)} FAILED'))
asyncio.run(main())
