# Taking scores out of a folder: select inside the folder, then Move › Library; and dragging one to "All scores"
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        await pg.evaluate("""async () => { const { db, setSetting } = await import('/js/db.js'); await setSetting('folders', [{ id: 'f1', name: 'Bach' }]); for (let i = 0; i < 4; i++) await db.put('scores', { id: 'sc' + i, title: 'Piece ' + (i + 1), composer: 'Test', pages: 2, added: Date.now() - i * 1000, folder: i < 3 ? 'f1' : undefined }); }""")
        await pg.reload(); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()"); await pg.wait_for_timeout(300)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        st = "const { db } = await import('/js/db.js'); return (await db.all('scores')).map(s => s.id + ':' + (s.folder || '-')).join(' ')"
        print('folders', await J("return [...document.querySelectorAll('.card.folder .ttl')].map(x => x.textContent)"), await J(st))
        await J("document.querySelector('.card.folder').click(); await sleep(300);")
        print('in folder', await J("return [document.querySelector('#folderTitle').textContent, document.querySelectorAll('#grid .card[data-sid]').length, !!document.querySelector('#libEdit').offsetParent]"))
        # select one by holding, Move
        c = pg.locator('.card[data-sid="sc0"]'); bx = await c.bounding_box()
        await pg.mouse.move(bx['x'] + 40, bx['y'] + 40); await pg.mouse.down(); await pg.wait_for_timeout(800); await pg.mouse.up(); await pg.wait_for_timeout(200)
        print('actions', await J("return [...document.querySelectorAll('#libActions button')].filter(b => b.offsetParent).map(b => b.textContent.trim() + (b.disabled ? '(off)' : ''))"))
        await pg.screenshot(path='/home/claude/shots/libout_sel.png')
        await J("document.querySelector('#libMove').click(); await sleep(400);")
        print('move sheet', await J("return [...document.querySelectorAll('#folderPick button')].map(b => b.textContent)"))
        await J("document.querySelector('#panel-folder [data-close]').click(); await sleep(400);")
        await J("document.querySelector('#libOutBtn').click(); await sleep(500);")
        print('after move out', await J(st), await J("return document.querySelectorAll('#grid .card[data-sid]').length"))
        # drag one onto All scores
        c = pg.locator('.card[data-sid="sc1"]'); bx = await c.bounding_box(); bb = None
        await pg.mouse.move(bx['x'] + 40, bx['y'] + 40); await pg.mouse.down(); await pg.wait_for_timeout(700)
        print('held', await J("return window.__dbgHold || 'none'"), await J("return [[...document.querySelectorAll('.card.picked')].map(c=>c.dataset.sid), !document.querySelector('#libActions').hidden, document.elementFromPoint(%d, %d)?.className]" % (bx['x'] + 40, bx['y'] + 40)))
        await pg.mouse.move(bx['x'] + 60, bx['y'] + 50); await pg.wait_for_timeout(60); await pg.mouse.move(bx['x'] + 90, bx['y'] + 30); await pg.wait_for_timeout(100)
        bb = await pg.locator('#libOut').bounding_box(); print('drop zone', bool(bb), await J("return [document.body.classList.contains('lib-dragging'), document.querySelector('#libOut').hidden, [...document.querySelectorAll('.card.picked')].map(c=>c.dataset.sid), !document.querySelector('#libActions').hidden]"))
        await pg.screenshot(path='/home/claude/shots/libout_drag.png')
        for i in range(1, 13): await pg.mouse.move(bx['x'] + 40 + (bb['x'] + 30 - bx['x'] - 40) * i / 12, bx['y'] + 40 + (bb['y'] + 15 - bx['y'] - 40) * i / 12); await pg.wait_for_timeout(30)
        await pg.mouse.up(); await pg.wait_for_timeout(600)
        print('after drag out', await J(st))
        # tapping empty space leaves selection
        c = pg.locator('.card[data-sid="sc2"]'); bx = await c.bounding_box()
        await pg.mouse.move(bx['x'] + 40, bx['y'] + 40); await pg.mouse.down(); await pg.wait_for_timeout(800); await pg.mouse.up(); await pg.wait_for_timeout(200)
        await pg.mouse.click(900, 700); await pg.wait_for_timeout(300)
        print('after tapping empty', await J("return [!document.querySelector('#libActions').hidden, document.querySelectorAll('.card.picked').length]"))
        print(errs); await b.close()
asyncio.run(main())
