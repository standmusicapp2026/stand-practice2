import asyncio, os, sys
from playwright.async_api import async_playwright
OUT = sys.argv[1]; W, H = int(os.environ.get('W', 852)), int(os.environ.get('H', 393))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': W, 'height': H}, is_mobile=True, has_touch=True, device_scale_factor=2, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true; try { localStorage.setItem("standLinkIntro", "1"); } catch {}')
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(2000)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelector('.tour-skip')?.click(); await sleep(300); const bs = [...document.querySelectorAll('[data-panel=\"tuner\"]')]; (bs.find((x) => x.offsetParent) || bs[0]).click(); await sleep(900); document.querySelector('.tour-skip')?.click();")
        os.makedirs(OUT, exist_ok=True)
        for t in ['tune', 'harm', 'drone']:
            await J("document.querySelector('#tunerTabs [data-tab=\"' + a + '\"]').click(); await sleep(700); document.querySelector('.tour-skip')?.click(); await sleep(200);", t)
            if t == 'tune': await J("document.querySelector('#tunerToggle')?.click(); await sleep(1500);")
            await pg.screenshot(path=f'{OUT}/{t}.png')
        await b.close()
asyncio.run(main())
