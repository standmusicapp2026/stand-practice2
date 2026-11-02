import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("window.__beats = 0; const led = document.querySelector('#metroLed'); new MutationObserver(() => { if (led.classList.contains('hit')) window.__beats++; }).observe(led, { attributes: true });")
        await J("document.querySelector('.tile[data-tile=\"metronome\"]').click(); await sleep(400); document.querySelector('#metroToggle').click(); await sleep(300); document.querySelector('[data-close]:not([hidden])')?.click();")
        async def beats(ms):
            b0 = await J("return window.__beats"); await pg.wait_for_timeout(ms); return (await J("return window.__beats")) - b0
        print('beats in 3s (80bpm≈4)', await beats(3000))
        for i in range(4):
            await J("document.querySelector('.tile[data-tile=\"tuner\"]').click(); await sleep(1200); document.querySelector('#panel-tuner [data-close]').click(); await sleep(300);")
        print('beats after tuner on/off x4', await beats(3000))
        await J("const { getCtx } = await import('/js/audio.js'); await getCtx().suspend();")
        print('beats after suspend (watchdog should wake)', await beats(4000))
        await J("const { healAudio } = await import('/js/audio.js'); await healAudio('reset');")
        print('beats after rebuilt sound system', await beats(3000))
        await J("document.querySelector('.tile[data-tile=\"tuner\"]').click(); await sleep(1500);")
        await J("const { healAudio } = await import('/js/audio.js'); await healAudio('reset'); await sleep(2000);")
        print('tuner still listening after rebuild', await J("return /Stop/.test(document.querySelector('#tunerToggle').textContent)"), 'beats', await beats(2000))
        print('errors', errs)
        await b.close()
asyncio.run(main())
