import asyncio, json, sys, base64, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(sys.argv[1],'rb').read()).decode()
        r = await pg.evaluate("""async ([src, si, xa, xb]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0,0,c.width,c.height); g.drawImage(img, 0, 0);
          globalThis.__accLog = []; globalThis.__accWin = null;
          const A = await O.analyse(c, true); const st = A.staves[si]; const f = A.work.f; const s = st._;
          const hs = s.heads.filter(h => h.cx > xa * f && h.cx < xb * f).map(h => ({ cx: Math.round(h.cx / f), left: Math.round(h.left / f), p: h.p, acc: h.acc }));
          const acc = (s.accTrace || []).filter(a => a.x0 > xa * f && a.x0 < xb * f).map(a => ({ ...a, x0: Math.round(a.x0 / f) }));
          const log = globalThis.__accLog.filter(a => a.x0 > xa * f && a.x0 < xb * f && a.y0 > s.top - s.sp * 4 && a.y0 < s.bottom + s.sp * 2).map(a => ({ ...a, x0: Math.round(a.x0 / f), k: a.k && [a.k.cls, +a.k.d.toFixed(3)] }));
          return { f, hs, acc, log }; }""", [data, int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])])
        print(json.dumps(r, indent=0)[:3000])
        await b.close()
asyncio.run(main())
