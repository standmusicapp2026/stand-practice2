import asyncio, base64, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        for png in sys.argv[1:]:
            data = 'data:image/png;base64,' + base64.b64encode(open(png, 'rb').read()).decode()
            r = await pg.evaluate("""async (src) => {
              const O = await import('/js/omr.js');
              const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const A = await O.analyse(c);
              const bars = []; for (const sys of A.systems) bars.push(...O.staffEvents(A.staves[sys[0]]));
              const tk = (it) => it.full ? 0 : Math.round(1920 / it.t * (2 - Math.pow(0.5, it.dots || 0)));
              const sums = bars.map((b) => O.fitBar(b, 1e9, { tupletsOnly: true }).reduce((a, it) => a + (it.full ? 0 : tk(it) * (it.tup ? it.tup.m / it.tup.n : 1)), 0));
              const C = [[4,4],[3,4],[2,4],[6,8],[2,2],[3,8],[9,8],[12,8],[5,4],[6,4],[3,2]]; const inner = bars.slice(1,-1); const fits = C.map((t) => { const tot = 1920*t[0]/t[1]; let n=0; for (const b of inner) { const f = O.fitBar(b, tot, { tupletsOnly: true }); const s2 = f.reduce((a, it) => a + (it.full ? tot : tk(it) * (it.tup ? it.tup.m / it.tup.n : 1)), 0); if (Math.abs(s2-tot)<1) n++; } return t.join('/') + ':' + (n/inner.length).toFixed(2); }); const hist = {}; for (const s of sums) hist[s] = (hist[s] || 0) + 1;
              return { fits, n: bars.length, hist, time0: A.staves[0].time || null, rows: bars.slice(0, 6).map((b) => b.map((it) => (it.rest ? 'r' : '') + it.t + '.'.repeat(it.dots) + (it.tup3 ? 'T' : '') + (it.tupN ? 'n' + it.tupN : '')).join(' ')) };
            }""", data)
            print(png.split('/')[-1], json.dumps(r))
        await b.close()
asyncio.run(main())
