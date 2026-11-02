# Notes on a page: laid with the Note tool, written in, closed to a tab, moved, coloured, kept, hidden
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('#inkBtn').click(); await sleep(400); document.querySelector('.ink-tool[data-tool=\"note\"]').click(); await sleep(200);")
        r = await J("const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]")
        await pg.touchscreen.tap(r[0] + 120, r[1] + 300); await pg.wait_for_timeout(600)
        print('note open, focused', await J("return [document.querySelectorAll('.snote').length, document.querySelector('.snote').className, document.activeElement && document.activeElement.className, document.querySelector('.ink-tool.on')?.dataset.tool]"))
        await pg.keyboard.type('Paulo: more bow at bar 12, lighter vibrato'); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/note_open.png')
        st = "const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.flatMap(r => r.items).filter(x => x.t === 'note').map(x => [x.c, x.txt, x.x, x.y])"
        await J("document.querySelectorAll('.snote-dot')[1].click(); await sleep(600);"); print('after dot', await J(st))
        await J("document.activeElement.blur(); await sleep(600);"); print('after blur', await J(st))
        await J("document.querySelector('.snote .snote-btn[aria-label=\"Close the note\"]').click(); await sleep(400);")
        print('closed', await J("return document.querySelector('.snote').className"), await J(st))
        t = await J("const r=document.querySelector('.snote-tab').getBoundingClientRect(); return [r.left + 13, r.top + 13]")
        # drag the tab
        await pg.mouse.move(*t); await pg.mouse.down(); await pg.mouse.move(t[0] + 200, t[1] + 80, steps=8); await pg.mouse.up(); await pg.wait_for_timeout(600)
        st = "const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.flatMap(r => r.items).filter(x => x.t === 'note').map(x => [x.c, x.txt, x.x, x.y])"
        print('stored', await J(st), 'page', await J("return document.querySelector('#pageLabel').textContent"))
        await pg.screenshot(path='/home/claude/shots/note_tab.png')
        # tap the tab: opens
        t = await J("const r=document.querySelector('.snote-tab').getBoundingClientRect(); return [r.left + 13, r.top + 13]")
        await pg.touchscreen.tap(*t); await pg.wait_for_timeout(500)
        print('reopened', await J("return document.querySelector('.snote').className"), await J(st))
        # undo the move and colour; leave and come back
        await J("document.querySelector('#inkDone').click(); await sleep(300); document.querySelector('#backBtn').click(); await sleep(800); document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        print('after reopen', await J("return [...document.querySelectorAll('.snote')].map(n => n.className + ' ' + n.querySelector('textarea').value)"))
        # tapping a closed note outside markings mode: opens, the page does not turn
        lab = await J("return document.querySelector('#pageLabel').textContent")
        t = await J("const r=document.querySelector('.snote-tab').getBoundingClientRect(); return [r.left + 13, r.top + 13]")
        await pg.touchscreen.tap(*t); await pg.wait_for_timeout(600)
        print('read without markings', await J("return document.querySelector('.snote').className"), 'page kept', lab == await J("return document.querySelector('#pageLabel').textContent"))
        await pg.screenshot(path='/home/claude/shots/note_read.png')
        # the eye hides notes
        await J("document.querySelector('#inkBtn').click(); await sleep(300); document.querySelector('#hideInkBtn').click(); await sleep(300);")
        print('hidden by the eye', await J("return getComputedStyle(document.querySelector('.notes-layer')).display"))
        await J("document.querySelector('#hideInkBtn').click(); await sleep(200); document.querySelector('.snote .snote-btn[aria-label=\"Throw the note away\"]').click(); await sleep(400);")
        print('thrown away', await J("return document.querySelectorAll('.snote').length"))
        await J("document.querySelector('#inkUndo').click(); await sleep(500);")
        print('undo brings back', await J("return document.querySelectorAll('.snote').length"))
        print('errors', errs[:5]); await b.close()
asyncio.run(main())
