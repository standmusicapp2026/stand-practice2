import asyncio, base64, sys
from playwright.async_api import async_playwright
async def main():
    ids = sys.argv[1].split(','); title = sys.argv[2] if len(sys.argv) > 2 else 'Bach Cello Suites'
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""async ([ids, title]) => { const C = await import('/js/covers.js');
          const out = document.createElement('canvas'); out.width = 620 * ids.length; out.height = 877; const g = out.getContext('2d');
          for (let i = 0; i < ids.length; i++) { const c = document.createElement('canvas'); c.width = 1240; c.height = 1754;
            await C.paintCover(c.getContext('2d'), { title, cover: { style: 'photo', photo: ids[i], sub: 'Paulo · 2026' } }, 1240, 1754); g.drawImage(c, i * 620, 0, 620, 877); }
          return out.toDataURL('image/png'); }""", [ids, title])
        open('/home/claude/shots/onecover.png','wb').write(base64.b64decode(r.split(',')[1])); await b.close()
asyncio.run(main())
