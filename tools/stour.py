import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for name, vp in [('ipad', {'width':1180,'height':820}), ('phone', {'width':390,'height':844})]:
            ctx = await b.new_context(viewport=vp, has_touch=True); pg = await ctx.new_page()
            errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
            J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
            await J("document.querySelector('#welGo')?.click(); await sleep(500); while (document.querySelector('.tour')) { document.querySelector('.tour-skip')?.click(); await sleep(300); } document.querySelector('.tile[data-tile=\"takes\"]').click(); await sleep(600); while (document.querySelector('.tour')) { document.querySelector('.tour-skip')?.click(); await sleep(300); }")
            await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/clip.webm'); await pg.wait_for_timeout(4000)
            await J("document.querySelector('#takeList li')?.click(); await sleep(1000); document.querySelector('#studioBtn').click(); await sleep(2500);")
            n = 0
            while await J("return !!document.querySelector('.tour')") and n < 8:
                await pg.screenshot(path=f'/home/claude/shots/stour_{name}_{n}.png'); n += 1
                await J("document.querySelector('.tour').click(); await sleep(500);")
            print(name, 'steps', n, errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
