import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; ST = int(sys.argv[3]) if len(sys.argv) > 3 else 0
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, st]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          globalThis.__graceDbg = []; const A = await O.analyse(c, true); const s = A.staves[st]._; return { g: globalThis.__graceDbg.filter(q => q.x > 900 && q.x < 1010), f: A.work.f, sp: s.sp, trace: (s.head.trace || []).filter(t => !t.a && !t.firstNote) }; }""", [data, CROP, ST])
        print('f', r['f'], 'sp', r['sp'], r['g']); [print(t) for t in r['trace']]
        await b.close()
asyncio.run(main())
