"""Screenshot harness: python3 shot.py <name> [js-steps-file] [--phone]
Opens the app in an iPad-sized Chromium, runs optional JS steps (separated by lines '---'),
waits between them, captures console errors, and saves /home/claude/shots/<name>.png"""
import sys, asyncio, json, os
from playwright.async_api import async_playwright

async def main():
    name = sys.argv[1]
    steps = []
    if len(sys.argv) > 2 and not sys.argv[2].startswith('--'):
        steps = [s.strip() for s in open(sys.argv[2]).read().split('\n---\n') if s.strip()]
    phone = '--phone' in sys.argv
    dark = '--dark' in sys.argv
    vw, vh = (390, 844) if phone else (1366, 1024)
    if '--portrait' in sys.argv: vw, vh = 1024, 1366
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=1 if not phone else 2,
                                  color_scheme='dark' if dark else 'light', has_touch=True,
                                  user_agent=('Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148' if phone else None))
        page = await ctx.new_page()
        if '--welcome' not in sys.argv: await page.add_init_script('window.__noTour = true;')
        errs = []
        page.on('console', lambda m: errs.append(f'[{m.type}] {m.text}') if m.type in ('error', 'warning') else None)
        page.on('pageerror', lambda e: errs.append(f'[pageerror] {e}'))
        await page.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html')
        await page.wait_for_timeout(1200)
        if '--welcome' not in sys.argv:
            await page.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }")
            await page.wait_for_timeout(700)
        for s in steps:
            if s.startswith('WAIT '):
                await page.wait_for_timeout(int(s[5:])); continue
            if s.startswith('SHOT '):
                await page.screenshot(path=f'/home/claude/shots/{s[5:].strip()}.png'); continue
            try:
                r = await page.evaluate('async () => {' + s + '}')
                if r is not None: print('=>', json.dumps(r)[:3000])
            except Exception as e:
                errs.append(f'[step error] {str(e)[:600]}')
            await page.wait_for_timeout(500)
        await page.screenshot(path=f'/home/claude/shots/{name}.png')
        for e in errs: print(e)
        await b.close()

asyncio.run(main())
