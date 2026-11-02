import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; ST = int(sys.argv[3]) if len(sys.argv) > 3 else 0
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        mime = 'image/jpeg' if FILE.endswith('.jpg') else 'image/png'
        data = 'data:' + mime + ';base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, st]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          globalThis.__keyDbg = []; globalThis.__digDbg = []; const A = await O.analyse(c, true); const s = A.staves[st]._; return { tm: [s.time, globalThis.__digDbg], kd: globalThis.__keyDbg.filter(q => q.a < 0 && q.p === 7 && q.x % 3 === 0).slice(0, 12), clef: s.clef, key: s.key, time: s.time, zone: s.head.zone, trace: s.head.trace }; }""", [data, CROP, ST])
        [print('kd', q) for q in r['kd']]
        print('TIME', r['tm']); print('clef', r['clef'], 'key', r['key'], 'time', r['time'])
        for z in r['zone'] or []: print('zone', z)
        for t in (r['trace'] or [])[:30]: print('trace', t)
        await b.close()
asyncio.run(main())
