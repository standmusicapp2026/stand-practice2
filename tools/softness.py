import asyncio, sys, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        for f in sys.argv[1:]:
            mime = 'image/jpeg' if f.endswith('.jpg') else 'image/png'
            d = 'data:' + mime + ';base64,' + base64.b64encode(open(f,'rb').read()).decode()
            r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              globalThis.__softLog = []; await O.analyse(c, false); return globalThis.__softLog[0]; }""", d)
            print(f.split('/')[-1], round(r, 2))
        await b.close()
asyncio.run(main())
