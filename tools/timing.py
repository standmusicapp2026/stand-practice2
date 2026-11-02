import asyncio, sys, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        for f in sys.argv[1:]:
            d = 'data:image/jpeg;base64,' + base64.b64encode(open(f,'rb').read()).decode()
            r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              let t = performance.now(); const a = await O.recognise(c, { lines: 'all' }); const t1 = performance.now() - t;
              t = performance.now(); await O.recogniseBest(c, { lines: 'all' }); return [Math.round(t1), Math.round(performance.now() - t), a.fitRead]; }""", d)
            print(f.split('/')[-1], r)
        await b.close()
asyncio.run(main())
