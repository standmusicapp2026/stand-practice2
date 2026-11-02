import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', '/home/claude/fixtures/vector8.pdf'); await pg.wait_for_timeout(3000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('[data-panel=\"settings\"]')?.click(); await sleep(300);")
        await J("document.querySelector('#pagesBtn, [data-panel=\"pages\"], #pgOpen')?.click(); await sleep(1200);")
        print('panel', await J("return !document.querySelector('#panel-pages').hidden"))
        cells = await J("return [...document.querySelectorAll('#pageGrid .pcell')].map(c=>{const r=c.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]})")
        print('cells', len(cells))
        # hold page 2 and drag after page 5
        a, z = cells[1], cells[4]
        await pg.mouse.move(*a); await pg.mouse.down(); await pg.wait_for_timeout(600)
        await pg.screenshot(path='/home/claude/shots/pg_held.png')
        for k in range(1, 15): await pg.mouse.move(a[0] + (z[0]+40-a[0])*k/14, a[1] + (z[1]-a[1])*k/14)
        await pg.screenshot(path='/home/claude/shots/pg_drag.png')
        await pg.mouse.up(); await pg.wait_for_timeout(800)
        print('order', await J("return [...document.querySelectorAll('#pageGrid .pcell')].length"), await J("return document.querySelector('#pgSave').hidden"))
        # hold page 1 -> selecting; tap pages 3 and 4; Delete bar
        cells = await J("return [...document.querySelectorAll('#pageGrid .pcell')].map(c=>{const r=c.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]})")
        await pg.mouse.move(*cells[0]); await pg.mouse.down(); await pg.wait_for_timeout(600); await pg.mouse.up(); await pg.wait_for_timeout(200)
        await pg.mouse.click(*cells[2]); await pg.wait_for_timeout(150); await pg.mouse.click(*cells[3]); await pg.wait_for_timeout(150)
        print('picked', await J("return document.querySelectorAll('#pageGrid .picked').length"), 'delbtn', await J("return !document.querySelector('#pgDelete').hidden"))
        await pg.screenshot(path='/home/claude/shots/pg_sel.png')
        await J("const { db } = await import('/js/db.js'); window.__old = (await db.all('scores'))[0];")
        await J("document.querySelector('#pgDelete').click(); await sleep(1800);")
        print('after delete', await J("return document.querySelectorAll('#pageGrid .pcell').length"), 'delbtn', await J("return document.querySelector('#pgDelete').hidden"))
        print('pageMap', await J("const { db } = await import('/js/db.js'); return (await db.all('scores'))[0].pageMap"))
        # an older copy of the score saved after the delete (a cover drawn again, the practice time): the pages stay deleted
        await J("const { db } = await import('/js/db.js'); await db.put('scores', { ...window.__old }); await sleep(300);")
        await pg.reload(); await pg.wait_for_timeout(2000)
        pm = await J("const { db } = await import('/js/db.js'); return (await db.all('scores'))[0].pageMap")
        print('pageMap after an old copy', pm)
        print('PASS' if pm == [2, 1, 5, 6, 7] else 'FAIL', 'deleted pages stay deleted')
        print(errs); await b.close()
asyncio.run(main())
