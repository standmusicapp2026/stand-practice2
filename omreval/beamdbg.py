import asyncio, base64, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        for png in sys.argv[1:]:
            data = 'data:image/png;base64,' + base64.b64encode(open(png, 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js'); globalThis.__omrRuns = []; globalThis.__omrDbg = {};
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const A = await O.analyse(c);
              const runs = globalThis.__omrRuns; const h = {}; for (const r of runs) { const k = Math.round(r * 10) / 10; h[k] = (h[k] || 0) + 1; }
              const most = {}; for (const q of globalThis.__omrDbg.beams || []) most[q.most] = (most[q.most] || 0) + 1;
              globalThis.__omrRuns = null; globalThis.__omrDbg = null;
              return { sp: A.staves.map((s) => s.sp)[0], hist: Object.entries(h).sort((a, b) => a[0] - b[0]), most };
            }""", data)
            print(png.split('/')[-1], json.dumps(r))
        await b.close()
asyncio.run(main())
