# Moving scores between folders sticks: an older copy of the score saved afterwards (the score that
# was open, a cover drawn again) does not put it back; a score whose folder is gone shows in the library
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT','8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf', '/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
        await pg.wait_for_timeout(2500)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        sid = await J("const c = document.querySelector('#grid .card:not(.folder)'); const id = c.dataset.sid; c.click(); await sleep(2500); window.__stale = await db.get('scores', id); document.querySelector('#backBtn, .back-btn, [data-act=back]')?.click(); await sleep(1200); return id;")
        # a folder, then move the score into it with the Move sheet
        await J("document.querySelector('#newFolder, #libNewFolder').click(); await sleep(500); document.querySelector('#folderName').value = 'Etudes'; document.querySelector('#folderSave').click(); await sleep(700); document.querySelector('#folderBack').click(); await sleep(600);")
        await J(f"document.querySelector('#folderSelect').click(); await sleep(300); document.querySelector('.card[data-sid=\"{sid}\"]').click(); await sleep(300); document.querySelector('#libMove').click(); await sleep(500); [...document.querySelectorAll('#folderPick .folder-row')].find(b => b.textContent === 'Etudes').click(); await sleep(800);")
        print('after move', await J(f"return (await db.get('scores', '{sid}')).folder ? 'in folder' : 'library'"))
        # an older copy of the score saved now (as the open score or a cover used to do)
        await J("const st = window.__stale; st.lastPage = 3; await db.put('scores', st); await sleep(300);")
        print('after a stale save', await J(f"return (await db.get('scores', '{sid}')).folder ? 'in folder' : 'library (WRONG)'"))
        # a score pointing at a folder that is not there shows in the library
        other = await J(f"const all = await db.all('scores'); const o = all.find(s => s.id !== '{sid}'); o.folder = 'gone-folder'; await db.put('scores', o); return o.id;")
        await pg.goto(base); await pg.wait_for_timeout(2500)
        print('after reload: moved score', await J(f"return (await db.get('scores', '{sid}')).folder ? 'in folder' : 'library (WRONG)'"))
        print('orphan shown in library', await J(f"return !!document.querySelector('#grid .card[data-sid=\"{other}\"]')"))
        print('folder card count', await J("return [...document.querySelectorAll('#grid .card.folder')].map(c => c.textContent)"))
        print(errs[:3]); await b.close()
asyncio.run(main())
