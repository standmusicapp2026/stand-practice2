import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; XA, XB = int(sys.argv[3]), int(sys.argv[4])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          globalThis.__graceDbg = []; await O.analyse(c, false); return globalThis.__graceDbg; }""", [data, CROP])
        for q in r:
            x = q.get('x', (q.get('ok') or [0])[0])
            if XA <= x <= XB: print(q)
        await b.close()
asyncio.run(main())
