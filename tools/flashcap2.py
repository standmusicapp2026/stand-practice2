# The first seconds after the app opens on a slow device (CPU 8x slower), every frame painted, to
# see a flash of another colour or a jump. argv: OUT scheme [theme] ; env SECOND=1 (welcome seen)
import asyncio, os, sys, base64
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); OUT = sys.argv[1]; SCHEME = sys.argv[2]; THEME = sys.argv[3] if len(sys.argv) > 3 else ''
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(color_scheme=SCHEME, viewport={'width': 1180, 'height': 820}); pg = await ctx.new_page()
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(1500)
        if THEME: await pg.evaluate("(t) => document.querySelector('#themeSeg button[data-theme=\"' + t + '\"]')?.click()", THEME); await pg.wait_for_timeout(1000)
        await pg.goto('about:blank'); await pg.evaluate("document.documentElement.style.background = '#ff00ff'")   # (magenta: what is not the page)
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 8})
        os.makedirs(OUT, exist_ok=True); frames = []
        def on(f):
            frames.append(f['data']); asyncio.ensure_future(cdp.send('Page.screencastFrameAck', {'sessionId': f['sessionId']}))
        cdp.on('Page.screencastFrame', on)
        await cdp.send('Page.startScreencast', {'format': 'jpeg', 'quality': 60, 'everyNthFrame': 1})
        await pg.goto(f'http://localhost:{PORT}/index.html', wait_until='load'); await pg.wait_for_timeout(4000)
        await cdp.send('Page.stopScreencast')
        for i, d in enumerate(frames): open(f'{OUT}/f{i:03d}.jpg', 'wb').write(base64.b64decode(d))
        print('frames', len(frames)); await b.close()
asyncio.run(main())
