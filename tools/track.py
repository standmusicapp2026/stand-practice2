import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; X = float(sys.argv[3])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        pg.on('pageerror', lambda e: print('ERR', e))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, X]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          const f0 = (await O.analyse(c, true)).work.f;
          globalThis.__headTrack = { x: X * f0, log: [] }; await O.analyse(c, true); return globalThis.__headTrack.log; }""", [data, CROP, X])
        for q in r: print(q)
        await b.close()
asyncio.run(main())
