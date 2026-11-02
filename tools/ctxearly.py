import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(3000)
        print(await pg.evaluate("() => window.__audioLog.map(e => e.what + ' ' + e.state)"))
        await b.close()
asyncio.run(main())
