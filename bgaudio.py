# Leaving Stand (the page hidden) with the metronome on: it keeps playing (beats go on, sound running);
# the tuner's microphone is let go and comes back. Leaving with nothing playing: the sound rests at
# once (suspended), and coming back the metronome starts as usual.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
HIDE = """(h) => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (h ? 'hidden' : 'visible') });
  document.dispatchEvent(new Event('visibilitychange')); }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}); await ctx.grant_permissions(['microphone'])
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const $=(q)=>document.querySelector(q); " + js + " }")
        S = lambda: pg.evaluate("() => window.__standSound()")
        await J("$('#welGo').click(); await sleep(400); $('.tour-skip')?.click(); await sleep(300);")
        # the tuner open, then the metronome on
        await J("const bs=[...document.querySelectorAll('[data-panel=\"tuner\"]')]; (bs.find((x)=>x.offsetParent)||bs[0]).click(); await sleep(400); if (!document.querySelector('#tunerToggle').textContent.match(/Stop/)) $('#tunerToggle').click(); await sleep(1500);")
        tun0 = await J("return $('#tunerToggle').textContent.trim();")
        await J("document.querySelectorAll('aside.panel:not([hidden]) [data-close]').forEach((x)=>x.click()); await sleep(300); const bs=[...document.querySelectorAll('[data-panel=\"metronome\"]')]; (bs.find((x)=>x.offsetParent)||bs[0]).click(); await sleep(400); $('#metroToggle').click(); await sleep(1500);")
        s0 = await S()
        await pg.evaluate(HIDE, True); await pg.wait_for_timeout(5000)
        s1 = await S()
        mic_hidden = await J("return $('#tunerToggle').textContent.trim();")
        await pg.evaluate(HIDE, False); await pg.wait_for_timeout(1500)
        s2 = await S()
        print('metronome before', s0, '\n  away 5 s', s1, '\n  back', s2, '\n  tuner', tun0, '->', mic_hidden)
        ok1 = s1['metro'] and s1['beats'] >= s0['beats'] + 4 and s1['state'] == 'running' and s1['rested'] == s0['rested']
        # nothing playing, leave
        await J("$('#metroToggle').click(); await sleep(500); document.querySelectorAll('aside.panel:not([hidden]) [data-close]').forEach((x)=>x.click()); await sleep(300);")
        await J("const bs=[...document.querySelectorAll('[data-panel=\"tuner\"]')]; (bs.find((x)=>x.offsetParent)||bs[0]).click(); await sleep(300); if ($('#tunerToggle').textContent.match(/Stop/)) $('#tunerToggle').click(); await sleep(500); document.querySelectorAll('aside.panel:not([hidden]) [data-close]').forEach((x)=>x.click()); await sleep(300);")
        r0 = (await S())['rested']
        await pg.evaluate(HIDE, True); await pg.wait_for_timeout(2500)
        s3 = await S()
        await pg.evaluate(HIDE, False); await pg.wait_for_timeout(1000)
        await J("const bs=[...document.querySelectorAll('[data-panel=\"metronome\"]')]; (bs.find((x)=>x.offsetParent)||bs[0]).click(); await sleep(300); $('#metroToggle').click(); await sleep(1500);")
        s4 = await S()
        print('quiet away', s3, '\n  metronome again', s4)
        ok2 = s3['state'] == 'suspended' and s3['rested'] == r0 + 1 and s4['metro'] and s4['state'] == 'running' and s4['beats'] > 1
        print('errors', errs[:3])
        print('PASS' if ok1 and ok2 and not errs else 'FAIL', 'leaving Stand: what plays keeps playing, nothing playing rests at once')
        await b.close()
asyncio.run(main())
