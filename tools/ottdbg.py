import asyncio, base64, json, sys
from playwright.async_api import async_playwright
F = sys.argv[1]
async def m():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        d = 'data:image/png;base64,' + base64.b64encode(open(F, 'rb').read()).decode()
        r = await pg.evaluate("""async (src) => { globalThis.__ottDbg = 1; const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode(); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0); const A = await O.analyse(c, false); return { dbg: globalThis.__ottDbg, st: A.staves.map((s) => s.ottavas), f: A.work && A.work.f }; }""", d)
        for x in r['dbg'] or []: print(x)
        print('staves', r['st'], 'f', r['f'])
        await b.close()
asyncio.run(m())
