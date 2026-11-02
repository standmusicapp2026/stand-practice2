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
          globalThis.__clefLog = []; const A = await O.analyse(c, true); const cl = globalThis.__clefLog; globalThis.__clefLog = null;
          return A.staves.map((st, i) => ({ keys: Object.keys(st).join(','), hk: st.head ? Object.keys(st.head).join(',') : '', cl: i ? null : cl, clef: st.clef, key: st.key, zone: st.head && st.head.zone, trace: (st.head && st.head.trace || []).filter((q) => q.a !== undefined || q.firstNote !== undefined).slice(0, 14) }));
        }""", [data, CROP])
        for st in r:
            print('clef', st['clef'], 'key', st['key'], st['cl'], st['keys'][:300], '|', st['hk'])
            for z in (st['zone'] or [])[:10]: print('  zone', json.dumps(z))
            for t in st['trace']: print('  key', json.dumps(t))
        await b.close()
asyncio.run(main())
