import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; X0, X1 = float(sys.argv[3]), float(sys.argv[4])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        mime = 'image/jpeg' if FILE.endswith('.jpg') else 'image/png'; data = 'data:' + mime + ';base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          globalThis.__omrDbg = {}; const A = await O.analyse(c, true); return { f: A.work.f, beams: globalThis.__omrDbg.beams }; }""", [data, CROP])
        f = r['f']
        for q in r['beams']:
            if X0 <= q['x'] / f <= X1: print({k: (round(v / f) if k in ('x', 'end') else v) for k, v in q.items()})
        await b.close()
asyncio.run(main())
