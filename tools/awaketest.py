# Battery: the screen may sleep only on the home screen with nothing going on and no touch for 3 min;
# a score, a tool open, the metronome, a recording keep it on. The page tells the app (standAwake).
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
NAT = "window.__aw = []; window.webkit = { messageHandlers: new Proxy({}, { get: (t, k) => t[k] || (t[k] = { postMessage(m) { if (k === 'standAwake') window.__aw.push(m.on); } }) }) };"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(NAT)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300);")
        # (time moved on 4 minutes, as if nobody had touched it)
        later = lambda: J("const real = Date.now; Date.now = () => real() + 240000; try { return window.__screenWanted(); } finally { Date.now = real; }")
        bad = []
        def check(ok, what): print(('ok   ' if ok else 'BAD  ') + what, flush=True); (None if ok else bad.append(what))
        check(await J("return window.__screenWanted()") is True, 'just touched: kept on')
        check(await later() is False, 'home, nothing going on, 4 min: may sleep')
        await J("const bs = [...document.querySelectorAll('[data-panel=\"metronome\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(500);")
        check(await later() is True, 'a tool open: kept on')
        await J("document.querySelector('#metroToggle').click(); await sleep(400); document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click()); await sleep(400);")
        check(await later() is True, 'the metronome playing, panel closed: kept on')
        await J("document.querySelector('#metroPillStop')?.click(); document.querySelector('#metroToggle').offsetParent || 0; await sleep(400);")
        await J("const m = await import('/js/main.js').catch(() => null);")
        st = await later()
        if st: await J("const bs = [...document.querySelectorAll('[data-panel=\"metronome\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(300); document.querySelector('#metroToggle').click(); await sleep(300); document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click()); await sleep(400);")
        check(await later() is False, 'metronome stopped, home: may sleep')
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/imslp12.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
        check(await later() is True, 'a score open: kept on')
        await pg.wait_for_timeout(16000)
        check(len(await J("return window.__aw")) >= 1 and (await J("return window.__aw"))[-1] is True, 'the app is told (last: on) ' + str(await J("return window.__aw")))
        print('errors', errs[:3]); print('PASS' if not bad and not errs else 'FAIL', 'the screen sleeps only when nothing is going on', bad)
        await b.close()
asyncio.run(main())
