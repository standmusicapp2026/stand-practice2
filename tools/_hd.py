import asyncio, json, sys, base64, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/png;base64,' + base64.b64encode(open(sys.argv[1],'rb').read()).decode()
        r = await pg.evaluate("""async ([src, si]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0,0,c.width,c.height); g.drawImage(img, 0, 0);
          const A = await O.analyse(c, true); const st = A.staves[si]; const f = A.work.f;
          return { f, sp: st.sp, heads: st.heads.map(h => [Math.round(h.x / f), h.p, h.acc ?? null]), accs: (st._.accs || []).map(a => [Math.round(a.x / f), a.p, a.v]) }; }""", [data, int(sys.argv[2])])
        print(json.dumps(r))
        await b.close()
asyncio.run(main())
