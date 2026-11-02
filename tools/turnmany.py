import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=3, has_touch=True, is_mobile=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        await pg.set_input_files('#importInput', '/home/claude/fixtures/vector8.pdf'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
        blank = []
        for k in list(range(7)) + list(range(7, -1, -1)):
            await pg.keyboard.press('ArrowRight' if k < 7 else 'ArrowLeft'); await pg.wait_for_timeout(700)
            ink = await pg.evaluate("""() => { const lab = window.__V ? window.__V.page : (document.querySelector('#stage .spread')?.dataset.page); const c = [...document.querySelectorAll('#stage canvas.art')].find(x => x.width); if (!c) return -1; const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4 * 97) if (d[i] < 128) n++; return [lab, n]; }""")
            blank.append(ink)
            await pg.screenshot(path=f'/home/claude/shots/turn_{len(blank)}.png')
        print('ink per page', blank)
        print(errs); await b.close()
asyncio.run(main())
