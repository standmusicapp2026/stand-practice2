import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
          globalThis.__graceDbg = []; await O.analyse(c, false); return globalThis.__graceDbg.filter(q => q.ok); }""", data)
        for q in r: print(q)
        await b.close()
asyncio.run(main())
