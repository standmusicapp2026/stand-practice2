import asyncio, json, sys, base64
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open('/home/claude/tc/raw-003.jpg','rb').read()).decode()
        r = await pg.evaluate("""async (src) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const crop = (x, y, w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0,0,w,h); g.drawImage(img, -x, -y); return c; };
          const f = (r) => r.bars[0].map(e => e.rest ? 'r' + e.t : e.ps.join('+') + '/' + e.t).join(' ');
          const a = await O.recogniseBest(crop(40, 615, 2303, 317), { lines: 'all' });
          const full = crop(0, 0, img.width, img.height); await O.analyse(full, false);
          const b = await O.recogniseBest(crop(40, 615, 2303, 317), { lines: 'all' });
          const a1 = await O.recognise(crop(40, 615, 2303, 317), { lines: 'all' });
          return [f(a), f(b), f(a1), a.fitRead, b.fitRead]; }""", data)
        print(r)
        await b.close()
asyncio.run(main())
