import asyncio, json, sys, base64
from playwright.async_api import async_playwright
FILE = sys.argv[1]; CROP = [int(v) for v in sys.argv[2].split(',')]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(800)
        data = 'data:image/jpeg;base64,' + base64.b64encode(open(FILE,'rb').read()).decode()
        r = await pg.evaluate("""async ([src, crop]) => { const O = await import('/js/omr.js'); const img = new Image(); img.src = src; await img.decode();
          const [x, y, w, h] = crop; const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, -x, -y);
          const A = await O.analyse(c, false); const out = [];
          for (const t of A.staves[0].texts) { const cv = document.createElement('canvas'); const W = Math.round(t.x1 - t.x0 + 8), H = Math.round(t.y1 - t.y0 + 8); cv.width = W; cv.height = H; cv.getContext('2d').drawImage(c, -(t.x0 - 4), -(t.y0 - 4)); out.push({ box: [t.x0, t.y0, t.x1, t.y1].map(Math.round), above: t.above, png: cv.toDataURL() }); }
          return out; }""", [data, CROP])
        from PIL import Image
        import io
        tiles = []
        for i, q in enumerate(r):
            print(i, q['box'], q['above'])
            tiles.append(Image.open(io.BytesIO(base64.b64decode(q['png'].split(',')[1]))))
        if tiles:
            W = max(t.width for t in tiles); H = sum(t.height + 4 for t in tiles)
            im = Image.new('RGB', (W, H), 'red'); y = 0
            for t in tiles: im.paste(t, (0, y)); y += t.height + 4
            im.save('/home/claude/shots/texts.png')
        await b.close()
asyncio.run(main())
