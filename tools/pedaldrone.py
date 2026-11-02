import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelector('[data-tab=\"drone\"]') && document.querySelector('[data-tab=\"drone\"]').click()")
        await pg.evaluate("document.querySelectorAll('.panel-body').forEach(x=>x.hidden=x.id!=='tab-drone')")
        await pg.evaluate("document.querySelector('#welcome')&&document.querySelector('#welcome').remove(); document.querySelector('#droneModeSeg [data-mode=stay]').click()")
        await pg.evaluate("document.querySelector('#droneToggle').click()"); await pg.wait_for_timeout(400)
        n = lambda: pg.evaluate("document.querySelector('#dronePillNote').textContent")
        print('start', await n())
        await pg.keyboard.press('PageDown'); await pg.wait_for_timeout(200); print('down', await n())
        await pg.keyboard.press('PageUp'); await pg.keyboard.press('PageUp'); await pg.wait_for_timeout(200); print('up x2', await n())
        await pg.select_option('#dronePedal', 'fifths'); await pg.evaluate("document.activeElement.blur()")
        await pg.keyboard.press('PageDown'); await pg.wait_for_timeout(200); print('fifth', await n())
        print('row visible', await pg.evaluate("!document.querySelector('#dronePedalRow').hidden"))
        print(errs); await b.close()
asyncio.run(main())
