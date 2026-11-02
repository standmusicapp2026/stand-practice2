import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, permissions=['microphone'])).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        r = await pg.evaluate("""async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
          document.querySelector('[data-mode=listen]').click(); await sleep(100);
          document.querySelector('#droneToggle').click(); await sleep(1500);
          const s = document.querySelector('#droneSens'); s.value = 0.9; s.dispatchEvent(new Event('input')); await sleep(100);
          const vis = !document.querySelector('#droneSensRow').hidden;
          document.querySelector('#droneToggle').click(); await sleep(300);
          return { vis, val: s.value, hear: document.querySelector('#droneHear').textContent }; }""")
        print(r, errs[:3]); await b.close()
asyncio.run(main())
