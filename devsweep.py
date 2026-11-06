# Every device size Stand runs on, both ways round: the home screen, Settings, a score, the tuner,
# the metronome; anything cut off (a button or text outside the screen with no way to scroll to it)
# or overlapping is listed, and a picture of each kept.
import asyncio, os, sys, json
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); OUT = sys.argv[1]
DEV = [('iPhone SE', 375, 667, True), ('iPhone 15', 393, 852, True), ('iPhone Pro Max', 440, 956, True),
       ('iPad mini', 744, 1133, False), ('iPad 11', 834, 1194, False), ('iPad 13', 1032, 1376, False)]
CHECK = """(sel) => { const out = []; const W = innerWidth, H = innerHeight;
  for (const e of document.querySelectorAll(sel + ' button, ' + sel + ' input, ' + sel + ' select, ' + sel + ' h2, ' + sel + ' label.btn')) {
    if (!e.offsetParent) continue; const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
    // (inside something that scrolls: fine if it can be scrolled to)
    let p = e.parentElement, scroll = false; while (p) { const cs = getComputedStyle(p); if (/(auto|scroll)/.test(cs.overflowY + cs.overflowX) && (p.scrollHeight > p.clientHeight + 1 || p.scrollWidth > p.clientWidth + 1)) { scroll = true; break; } p = p.parentElement; }
    if (scroll) continue;
    if (r.right > W + 1 || r.left < -1 || r.bottom > H + 1 || r.top < -1) out.push((e.id || e.textContent.trim().slice(0, 24) || e.className).toString().slice(0, 30) + ' @' + Math.round(r.left) + ',' + Math.round(r.top));
  } return out.slice(0, 8); }"""
async def main():
    async with async_playwright() as p:
        b = await getattr(p, os.environ.get('BR', 'chromium')).launch()
        os.makedirs(OUT, exist_ok=True); problems = []
        for name, w, h, phone in DEV:
            for land in (False, True):
                W, H = (h, w) if land else (w, h)
                kw = dict(viewport={'width': W, 'height': H}, has_touch=True)
                if phone: kw.update(is_mobile=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
                ctx = await b.new_context(**kw); pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
                await pg.add_init_script('window.__noTour = true; try { localStorage.setItem("standLinkIntro", "1"); } catch {}')
                await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1800)
                J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
                tag = f"{name.replace(' ', '')}-{'land' if land else 'port'}"
                await pg.screenshot(path=f'{OUT}/{tag}-welcome.png')
                await J("document.querySelector('#welGo')?.click(); await sleep(500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
                await pg.screenshot(path=f'{OUT}/{tag}-home.png')
                cut = await pg.evaluate(CHECK, 'body')
                if cut: problems.append((tag, 'home', cut))
                if not phone:
                    await pg.set_input_files('#importInput', ['/home/claude/fixtures/imslp12.pdf'])
                    try:
                        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
                        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
                        await pg.screenshot(path=f'{OUT}/{tag}-score.png')
                        cut = await pg.evaluate(CHECK, '#score')
                        if cut: problems.append((tag, 'score', cut))
                    except Exception as e: problems.append((tag, 'score', str(e)[:80]))
                for pn in ['tuner', 'metronome', 'app']:
                    ok = await J("const bs = [...document.querySelectorAll('[data-panel=\"' + a + '\"]')]; const b = bs.find((x) => x.offsetParent) || bs[0]; if (!b) return false; b.click(); await sleep(700); document.querySelector('.tour-skip')?.click(); await sleep(200); return !document.querySelector('#panel-' + a).hidden;", pn)
                    if not ok: continue
                    await pg.screenshot(path=f'{OUT}/{tag}-{pn}.png')
                    cut = await pg.evaluate(CHECK, '#panel-' + pn)
                    if cut: problems.append((tag, pn, cut))
                    await J("document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click()); await sleep(400);")
                if errs: problems.append((tag, 'errors', errs[:2]))
                print(tag, 'done', flush=True)
                await ctx.close()
        print('PROBLEMS'); [print(' ', x) for x in problems]
        await b.close()
asyncio.run(main())
