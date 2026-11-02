# the staves found on a picture: python3 stavesof.py IMG
import asyncio, sys, os, base64, json
from playwright.async_api import async_playwright
F = sys.argv[1]
async def main():
    data = ('data:image/jpeg;base64,' if F.endswith('.jpg') else 'data:image/png;base64,') + base64.b64encode(open(F, 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(800)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate("""async (src) => {
          const O = await import('/js/omr.js');
          const img = new Image(); img.src = src; await img.decode();
          const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
          globalThis.__fsDbg = []; globalThis.__stfDbg = []; const A = await O.analyse(c, true); globalThis.__fs = globalThis.__fsDbg;
          return { stf: globalThis.__stfDbg, fs: globalThis.__fs, f: A.work && A.work.f, sp: A.sp, st: A.staves.map((s) => [Math.round(s.top), Math.round(s.bottom), Math.round(s.x0), Math.round(s.x1), +s.sp.toFixed(1), s.heads.length]) };
        }""", data)
        print('f', r['f'], 'sp', r['sp'])
        if os.environ.get('STF'): print(json.dumps(r['stf']))
        if os.environ.get('FS'):
            Y0, Y1 = map(float, os.environ['FS'].split(','))
            for d in r['fs']:
                if 'staves' in d:
                    [print('S', q) for q in d['staves'] if Y0 - 100 <= q[0] <= Y1]; continue
                print('SW', d['SW'], 'sp', d['sp'])
                for g in d['groups']:
                    if Y0 <= g[1][0] <= Y1: print('G', g)
                for t in d['tracks']:
                    if Y0 - 200 <= t[2] <= Y1 + 200: print('T', t)
        for s in r['st']: print(s)
        await b.close()
asyncio.run(main())
