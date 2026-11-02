# A name typed for a notebook (or a score) shows under its picture the moment you go back, and a
# notebook's cover picture is made again with the new name
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); await sleep(300);")
        before = await J("const s = (await db.all('scores'))[0]; return [s.title, s.thumb ? s.thumb.size : 0, s.thumbAt || 0];")
        await J("document.querySelector('#score [data-panel=settings]').click(); await sleep(400); const i = document.querySelector('#metaTitle'); i.value = 'Harmonia 3'; i.dispatchEvent(new Event('input'));")
        quick = await J("document.querySelector('#backBtn').click(); await sleep(60); return [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x => x.textContent);")
        await pg.wait_for_timeout(4000)
        after = await J("const s = (await db.all('scores'))[0]; const f = await db.get('files', s.fileId); return [s.title, s.thumb ? s.thumb.size : 0, s.thumbAt || 0, f.title, s.thumbTitle];")
        print('before', before, 'at once', quick, 'after', after)
        ok = 'Harmonia 3' in quick and after[0] == 'Harmonia 3' and after[3] == 'Harmonia 3' and after[2] > before[2] and after[4] == 'Harmonia 3'
        # opened and closed again with nothing changed: the cover is not made again
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2000); document.querySelector('#backBtn').click(); await sleep(2500);")
        again = await J("const s = (await db.all('scores'))[0]; return s.thumbAt || 0;")
        ok = ok and again == after[2]
        print('PASS' if ok else 'FAIL', 'notebook name shows at once, cover made again'); print(errs[:3])
        await b.close()
asyncio.run(main())
