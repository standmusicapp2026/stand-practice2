# How busy Stand keeps the device when nobody touches it, screen by screen: main-thread time per
# second, frames drawn per second (requestAnimationFrame), timers fired per second, and where from.
import asyncio, os, sys, json
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
SPY = '''(() => { const C = window.__spy = { raf: {}, tmo: {}, iv: {} }; const where = () => { const s = (new Error().stack || '').split('\\n').slice(3, 6).map((l) => (l.match(/\\/js\\/([^?:]+:\\d+)/) || [])[1]).filter(Boolean); return s.join(' < ') || '?'; };
  const R = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = (f) => { const w = where(); C.raf[w] = (C.raf[w] || 0) + 1; return R(f); };
  const T = window.setTimeout.bind(window); window.setTimeout = (f, ms, ...a) => { if (typeof f === 'function') { const w = where() + ' (' + (ms | 0) + 'ms)'; C.tmo[w] = (C.tmo[w] || 0) + 1; } return T(f, ms, ...a); };
  const I = window.setInterval.bind(window); window.setInterval = (f, ms, ...a) => { const w = where() + ' (' + (ms | 0) + 'ms)'; const g = typeof f === 'function' ? (...x) => { C.iv[w] = (C.iv[w] || 0) + 1; return f(...x); } : f; return I(g, ms, ...a); };
})();'''
async def measure(pg, cdp, label, secs=8):
    await pg.evaluate("() => { const C = window.__spy; C.raf = {}; C.tmo = {}; C.iv = {}; }")
    m0 = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}
    await pg.wait_for_timeout(secs * 1000)
    m1 = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}
    spy = await pg.evaluate("() => window.__spy")
    d = lambda k: (m1.get(k, 0) - m0.get(k, 0)) / secs
    top = lambda o: sorted(o.items(), key=lambda x: -x[1])[:4]
    print(f"== {label}: busy {d('TaskDuration')*1000:.0f} ms/s, script {d('ScriptDuration')*1000:.0f} ms/s, layouts {d('LayoutCount'):.1f}/s, styles {d('RecalcStyleCount'):.1f}/s, frames(raf) {sum(spy['raf'].values())/secs:.1f}/s, timers {sum(spy['tmo'].values())/secs:.1f}/s, intervals {sum(spy['iv'].values())/secs:.1f}/s", flush=True)
    for k, v in top(spy['raf']): print(f"     raf {v/secs:5.1f}/s  {k}")
    for k, v in top(spy['tmo']): print(f"     tmo {v/secs:5.1f}/s  {k}")
    for k, v in top(spy['iv']): print(f"     iv  {v/secs:5.1f}/s  {k}")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        phone = os.environ.get('PHONE')
        kw = dict(viewport={'width': 393, 'height': 852}, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)') if phone else dict(viewport={'width': 1180, 'height': 820}, has_touch=True)
        ctx = await b.new_context(**kw); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true; try { localStorage.setItem("standLinkIntro", "1"); } catch {}'); await pg.add_init_script(SPY)
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Performance.enable')
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click();")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/imslp12.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000); await pg.wait_for_timeout(8000)
        await measure(pg, cdp, 'home, idle (after import settled)')
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('.tour-skip')?.click();")
        await pg.wait_for_timeout(6000)
        await measure(pg, cdp, 'score open, idle')
        await measure(pg, cdp, 'score open, idle (later)')
        await pg.wait_for_timeout(20000)
        await measure(pg, cdp, 'score open, idle (30 s later)')
        for name, sel in [('metronome panel open (not playing)', 'metro'), ('tuner open', 'tuner')]:
            await J("const bs = [...document.querySelectorAll('[data-panel=\"' + a + '\"]')]; (bs.find((x) => x.offsetParent) || bs[0])?.click(); await sleep(800);", sel)
            await measure(pg, cdp, name)
            await J("document.querySelectorAll('.panel:not([hidden]) [data-close]').forEach((x) => x.click()); await sleep(600);")
        await measure(pg, cdp, 'score open again, panels closed')
        await b.close()
asyncio.run(main())
