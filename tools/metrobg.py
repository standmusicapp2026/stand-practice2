# The metronome pauses when Stand goes to the background and comes back where it was; the beat-one
# flash is seen above the metronome on the iPhone (whose metronome fills the screen)
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148', has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("document.querySelector('[data-panel=metronome], [data-tile=metronome]')?.click(); await sleep(800);")
        await J("document.querySelector('#flashOn').checked = true; document.querySelector('#flashOn').dispatchEvent(new Event('change')); await sleep(100);")
        await J("document.querySelector('#metroToggle, #metroPlay, [data-metro=play]')?.click(); await sleep(1500);")
        st = await J("""const f = document.querySelector('#flash'); const p = [...document.querySelectorAll('.panel')].find(x => !x.hidden);
          return { panel: p && p.id, panelZ: p && getComputedStyle(p).zIndex, flashZ: getComputedStyle(f).zIndex, running: !!document.querySelector('#metroToggle.on, #metroPlay.on, .metro-on') }""")
        print('screen', st)
        # flash seen on beat one: the element on top at the middle of the screen while flashing
        seen = await J("""let n = 0; const f = document.querySelector('#flash'); const t0 = performance.now();
          while (performance.now() - t0 < 3500) { if (f.classList.contains('on')) n++; await sleep(5); } return n""")
        print('flash frames seen', seen)
        hide = """Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); await sleep(1500);"""
        show = """Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); await sleep(1500);"""
        clicks = "return (globalThis.__clicks || []).length ? +globalThis.__clicks[globalThis.__clicks.length - 1].t.toFixed(2) : null"
        print('last click before', await J(clicks))
        await J(hide)
        a = await J(clicks); await J("await sleep(1500);"); b2 = await J(clicks)
        print('hidden: clicks scheduled stop', a, b2, 'same' if a == b2 else 'STILL CLICKING')
        await J(show)
        c = await J(clicks)
        print('back: clicking again', c, 'ok' if c and b2 and c > b2 else 'NOT RESTARTED')
        print(errs[:3]); await b.close()
asyncio.run(main())
