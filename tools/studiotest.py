import asyncio, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]')?.click(); await sleep(500);")
        await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/face_clip.webm'); await pg.wait_for_timeout(5000)
        await J("document.querySelector('#takeList li')?.click(); await sleep(1200); document.querySelector('#studioBtn').click(); await sleep(2500);")
        await pg.screenshot(path='/home/claude/shots/stt_empty.png')
        img = base64.b64encode(open('/home/claude/tc/raw-002.jpg', 'rb').read()).decode()
        r = await pg.evaluate("""async (src) => { const S = await import('/js/studio.js'); const img = new Image(); img.src = 'data:image/jpeg;base64,' + src; await img.decode();
          const c = document.createElement('canvas'); c.width = 2080; c.height = 620; c.getContext('2d').drawImage(img, -150, -500);
          const o = await S._addScoreFrom(c); return { bars: o.layout.bars.length, width: o.layout.width }; }""", img)
        print('score', r)
        for name, t in [('start', 0.05), ('mid', 4.0), ('end', 7.9)]:
            await J(f"const ST = (await import('/js/studio.js'))._studio; ST.media.currentTime = {t}; await sleep(700); (await import('/js/studio.js'))._frame(); await sleep(200);")
            await pg.screenshot(path=f'/home/claude/shots/stt_{name}.png')
        await J("const S = await import('/js/studio.js'); const o = S._studio.P.overlays[0]; o.look = 'lines'; S._studio.media.currentTime = 7.9; await sleep(600); S._frame();")
        await pg.screenshot(path='/home/claude/shots/stt_lines_end.png')
        # the look: Auto
        await J("const S = await import('/js/studio.js'); S._studio.sel = null; document.querySelector('#stFormatBtn')?.click(); await sleep(500);")
        await J("const b = [...document.querySelectorAll('#stSide button')].find(x => /Auto/.test(x.textContent)); if (b) b.click(); await sleep(6000);")
        await pg.screenshot(path='/home/claude/shots/stt_auto.png')
        print(await J("const S = await import('/js/studio.js'); return S._studio.P.look;"))
        print(errs); await b.close()
asyncio.run(main())
