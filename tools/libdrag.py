# Library: hold a score and drag it onto another; on release a New folder sheet asks for the name
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); for (let i = 0; i < 4; i++) await db.put('scores', { id: 'sc' + i, title: 'Piece ' + (i + 1), composer: i < 2 ? 'J. S. Bach' : 'Other', pages: 2, added: Date.now() - i * 1000 }); }""")
        await pg.reload(); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
        a = await pg.locator('.card[data-sid="sc0"]').bounding_box(); t = await pg.locator('.card[data-sid="sc1"]').bounding_box()
        await pg.mouse.move(a['x'] + 40, a['y'] + 40); await pg.mouse.down(); await pg.wait_for_timeout(700)
        for k in range(1, 16):
            await pg.mouse.move(a['x'] + 40 + (t['x'] - a['x']) * k / 15, a['y'] + 40 + (t['y'] - a['y']) * k / 15); await pg.wait_for_timeout(20)
        print('over', await pg.evaluate("() => document.querySelector('.card[data-sid=\"sc1\"]').classList.contains('drop-on')"))
        await pg.screenshot(path='/home/claude/shots/lib_drag.png')
        await pg.mouse.up(); await pg.wait_for_timeout(500)
        print('sheet', await pg.evaluate("() => [document.querySelector('#folderSheetTitle').textContent, document.querySelector('#folderName').value, !document.querySelector('#panel-folder').hidden]"))
        await pg.screenshot(path='/home/claude/shots/lib_drag_sheet.png')
        await pg.locator('#folderSave').click(); await pg.wait_for_timeout(500)
        print(await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); const all = await db.all('scores'); return { inFolder: all.filter(s => s.folder).map(s => s.id), title: document.querySelector('#folderTitle').textContent }; }"""))
        print(errs); await b.close()
asyncio.run(main())
