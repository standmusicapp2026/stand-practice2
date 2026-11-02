import asyncio, json, sys, base64, os
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop]) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop;
          const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(img, -x, -y);
          globalThis.__accLog = []; const A = await O.analyse(c, false); const log = globalThis.__accLog; globalThis.__accLog = null;
          return { log: log.map((q) => ({ ...q, k: q.k && { cls: q.k.cls, d: +q.k.d.toFixed(3) } })), heads: A.staves.map((st) => (st.heads || []).map((hd) => [Math.round(hd.x ?? hd.cx), hd.p, hd.acc])) };
        }""", [data, CROP])
        print('heads', r['heads'])
        for a in r['log']: print('  comp', json.dumps(a))
        await b.close()
asyncio.run(main())
