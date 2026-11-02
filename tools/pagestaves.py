import asyncio, json, sys, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        for i in range(4):
            data = 'data:image/jpeg;base64,' + base64.b64encode(open(f'/home/claude/tc/raw-00{i}.jpg','rb').read()).decode()
            r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
              const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; c.getContext('2d').drawImage(img, 0, 0);
              const A = await O.analyse(c, false); return { sys: A.systems, st: A.staves.map(s => [Math.round(s.x0), Math.round(s.top), Math.round(s.x1), Math.round(s.bottom), +s.sp.toFixed(1)]) }; }""", data)
            print(i, json.dumps(r))
        await b.close()
asyncio.run(main())
