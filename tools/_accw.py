import asyncio, json, sys, base64, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(sys.argv[1],'rb').read()).decode()
        r = await pg.evaluate("""async ([src, si, xh]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0,0,c.width,c.height); g.drawImage(img, 0, 0);
          let A = await O.analyse(c, true); const f = A.work.f; const hd = A.staves[si]._.heads.find(h => Math.abs(h.cx / f - xh) < 4);
          globalThis.__accWin = [hd.cx, hd.cy]; A = await O.analyse(c, true); const out = globalThis.__accWin.slice(2); globalThis.__accWin = null;
          return { sp: A.staves[si].sp, hd: [hd.cx, hd.cy, hd.left], out: out.filter(q => q[2] === q[0] || q[3] < 0.5).slice(0, 60) }; }""", [data, int(sys.argv[2]), int(sys.argv[3])])
        print(json.dumps(r))
        await b.close()
asyncio.run(main())
