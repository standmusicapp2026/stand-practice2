# The eyes set-up end to end in the browser, with a still face as the camera
import asyncio
from playwright.async_api import async_playwright
Y4M = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/faces/face.y4m'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-video-capture={Y4M}', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, permissions=['camera'])
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        await pg.evaluate("() => document.querySelector('[data-panel=\"app\"]')?.click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { const f = document.querySelector('#followOn'); f.checked = true; f.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(300)
        vis = await pg.evaluate("() => ({ body: !document.querySelector('#followBody').hidden, state: document.querySelector('#eyesState').textContent })")
        print('settings', vis)
        await pg.evaluate("() => { const f = document.querySelector('#followEyes'); f.checked = true; f.dispatchEvent(new Event('change')); }"); await pg.wait_for_timeout(500)
        print('overlay', await pg.evaluate("() => !document.querySelector('#eyeCal').hidden"))
        await pg.wait_for_timeout(4000)
        print('intro', await pg.evaluate("() => [document.querySelector('#eyeCalState').textContent, document.querySelector('#eyeCalCam').className]"))
        await pg.screenshot(path='/home/claude/shots/eyecal_intro.png')
        await pg.wait_for_timeout(4000)
        print('intro', await pg.evaluate("() => [document.querySelector('#eyeCalState').textContent, document.querySelector('#eyeCalCam').className]"))
        await pg.screenshot(path='/home/claude/shots/eyecal_intro.png')
        await pg.wait_for_timeout(4000)
        print('intro', await pg.evaluate("() => [document.querySelector('#eyeCalState').textContent, document.querySelector('#eyeCalCam').className]"))
        await pg.screenshot(path='/home/claude/shots/eyecal_intro.png')
        await pg.evaluate("() => document.querySelector('#eyeCalGo').click()")
        for i in range(90):
            await pg.wait_for_timeout(1000)
            t = await pg.evaluate("() => [window.__ec.phase, document.querySelector('#eyeCalTitle').textContent, document.querySelector('#eyeCalText').textContent.slice(0, 90)]")
            if i % 5 == 0: print(i, t)
            if t[0] in ('result', 'intro') and i > 2: break
        print('end', t)
        await pg.screenshot(path='/home/claude/shots/eyecal.png')
        print(await pg.evaluate("() => JSON.stringify((JSON.parse(localStorage.getItem('stand-settings') || '{}').eyesCal) || null).slice(0, 200)"))
        print(await pg.evaluate('() => JSON.stringify(window.__ecCheck)')); print(await pg.evaluate('() => document.querySelectorAll(".eyecal-hit").length')); print(errs); await b.close()
asyncio.run(main())
