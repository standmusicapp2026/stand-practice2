import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]; XA, XB = float(sys.argv[3]), float(sys.argv[4]); ST = int(sys.argv[5]) if len(sys.argv) > 5 else 0
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop, xa, xb, st]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          const A = await O.analyse(c, true); const S = A.staves[st]; const s = S._; const f = A.work.f;
          return { f, sp: s.sp, heads: s.heads.filter(hd => hd.cx / f >= xa && hd.cx / f <= xb).map(hd => ({ x: Math.round(hd.cx / f), y: Math.round(hd.cy / f), p: hd.p, kind: hd.kind, hollow: hd.hollow, ring: !!hd.ringHead, wRow: +(hd.wRow / s.sp).toFixed(2), stem: hd.stem && { x: Math.round(hd.stem.x / f), up: hd.stem.up, len: +(hd.stem.len / s.sp).toFixed(1), endY: Math.round(hd.stem.end / f) }, beams: hd.beams, dots: hd.dots, right: Math.round(hd.right / f), bg: hd.bg, tup: hd.tupN })) }; }""", [data, CROP, XA, XB, ST])
        print('f', r['f'], 'sp', r['sp'])
        for q in r['heads']: print(q)
        await b.close()
asyncio.run(main())
