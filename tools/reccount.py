# Recording: 1, 2, 3, 4 on the screen, silent; the metronome is not started by itself, waits paused
# in the recording bar at the set tempo, and plays when tapped (stopped with the recording)
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True, permissions=['camera', 'microphone'])
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
        mrun = lambda: pg.evaluate("() => !document.querySelector('#metroPill').hidden")
        await pg.evaluate("() => { document.querySelector('#recBtn').click(); }"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.querySelector('#recAudio').click()"); await pg.wait_for_timeout(300)
        seen = []
        for k in range(30):
            v = await pg.evaluate("() => { const c = document.querySelector('#recCount'); return c.hidden ? '' : c.querySelector('b').textContent; }")
            if v and (not seen or seen[-1] != v): seen.append(v)
            if k == 4: await pg.screenshot(path='/tmp/claude-0/fz/reccount.png')
            await pg.wait_for_timeout(150)
        m1 = await mrun()
        await pg.screenshot(path='/tmp/claude-0/fz/recbar.png')
        bpm = await pg.evaluate("() => document.querySelector('#recMetroBpm').textContent")
        await pg.evaluate("() => document.querySelector('#recMetro').click()"); await pg.wait_for_timeout(800)
        m2 = await mrun(); on = await pg.evaluate("() => document.querySelector('#recMetro').classList.contains('on')")
        await pg.evaluate("() => document.querySelector('#recStop').click()"); await pg.wait_for_timeout(2500)
        m3 = await mrun()
        print('count', seen, 'metro before tap', m1, 'bpm', bpm, 'after tap', m2, on, 'after stop', m3)
        ok = seen == ['1', '2', '3', '4'] and not m1 and m2 and on and not m3
        print('PASS' if ok else 'FAIL', 'count-in on screen, metronome only when tapped'); print(errs[:3])
        await b.close()
asyncio.run(main())
