# A cover that came out black (or whose picture is lost) is made again by itself
import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT','8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf', '/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
        await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); const all = await db.all('scores');
          const c = document.createElement('canvas'); c.width = 360; c.height = 500; const g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, 360, 500);
          all[0].thumb = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.8)); await db.put('scores', all[0]);
          all[1].thumb = new Blob([new Uint8Array([1, 2, 3])], { type: 'image/jpeg' }); await db.put('scores', all[1]); }""")
        await pg.goto(base); await pg.wait_for_timeout(9000)
        r = await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); const S = await import('/js/score.js'); const out = [];
          for (const s of await db.all('scores')) { const u = URL.createObjectURL(s.thumb); const im = new Image(); const ok = await new Promise(res => { im.onload = () => res(!S.looksBlack(im)); im.onerror = () => res('broken'); im.src = u; }); out.push([s.title.slice(0, 20), ok, s.thumb.size]); }
          return out; }""")
        print(json.dumps(r)); print('errors', errs[:3]); await b.close()
asyncio.run(main())
