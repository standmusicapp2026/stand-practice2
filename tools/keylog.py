import asyncio, json, sys, base64, os
from playwright.async_api import async_playwright
FILE = sys.argv[1]; Y = [int(v) for v in sys.argv[2].split(',')]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async (src) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0);
          globalThis.__keyLog = []; globalThis.__clefLog = []; const A = await O.analyse(c, false); const L = globalThis.__keyLog; const CL = globalThis.__clefLog; globalThis.__keyLog = null; globalThis.__clefLog = null;
          return { CL, L, scale: A.scale, staves: A.staves.map((st) => [Math.round(st.top), st.clef, st.key, Math.round(st.bottom), +st.sp.toFixed(1)]) };
        }""", data)
        print(r['scale'], r['staves'])
        for q in r['L']:
            if Y[0] <= q['y'] <= Y[1]: print(json.dumps(q))
        await b.close()
asyncio.run(main())
