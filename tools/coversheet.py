import asyncio, base64, sys
from playwright.async_api import async_playwright
TITLE = sys.argv[1] if len(sys.argv) > 1 else 'Bach Cello Suites'
SUB = sys.argv[2] if len(sys.argv) > 2 else 'Paulo · 2026'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("""async ([title, sub]) => {
          const C = await import('/js/covers.js');
          const w = 310, h = 438, cols = 6, rows = Math.ceil(C.COVER_PHOTOS.length / cols);
          const out = document.createElement('canvas'); out.width = cols * (w + 10); out.height = rows * (h + 26);
          const g = out.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, out.width, out.height);
          let i = 0;
          for (const ph of C.COVER_PHOTOS) {
            const c = document.createElement('canvas'); c.width = w * 2; c.height = h * 2;
            await C.paintCover(c.getContext('2d'), { title, cover: { style: 'photo', photo: ph.id, sub, dir: 'down' } }, c.width, c.height);
            const x = (i % cols) * (w + 10), y = Math.floor(i / cols) * (h + 26);
            g.drawImage(c, x, y, w, h); g.fillStyle = '#000'; g.font = '13px sans-serif'; g.fillText(ph.id + ' ' + ph.label, x + 2, y + h + 16); i++;
          }
          return out.toDataURL('image/png');
        }""", [TITLE, SUB])
        open('/home/claude/shots/coversheet.png','wb').write(base64.b64decode(r.split(',')[1])); print(errs); await b.close()
asyncio.run(main())
