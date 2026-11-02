# Pages panel: add pages from a PDF and a photo, into a PDF score, a photo score and a notebook
import asyncio
from playwright.async_api import async_playwright
F = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True, accept_downloads=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        lab = lambda: J("return document.querySelector('#pageLabel').textContent")
        async def add(files):
            await J("document.querySelector('[data-panel=\"pages\"], #pagesBtn, #nbPagesBtn')?.click(); await sleep(300);")
            if await J("return document.querySelector('#panel-pages').hidden"):
                await J("const b=[...document.querySelectorAll('button')].find(x=>x.dataset.panel==='pages'||/^Pages$/.test(x.textContent.trim())); b&&b.click(); await sleep(400);")
            await pg.set_input_files('#pgAddInput', files)
            await pg.wait_for_function("/added|could not|No pages/.test(document.querySelector('#toast').textContent)", timeout=120000)
            await pg.wait_for_timeout(2500)
            return await J("return document.querySelector('#toast').textContent")
        # PDF score
        await pg.set_input_files('#importInput', [F + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(3000);")
        await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(1000)
        print('pdf score at', await lab())
        print(await add([F + 'scan10.pdf', F + 'photo.jpg']), '->', await lab())
        print('grid', await J("return document.querySelectorAll('#pageGrid > *').length"))
        await pg.screenshot(path='/home/claude/shots/addpages_pdf.png')
        await J("document.querySelector('#panel-pages [data-close]').click(); await sleep(300); document.querySelector('#backBtn').click(); await sleep(800); document.querySelector('#grid .card:not(.folder)').click(); await sleep(3000);")
        print('reopened', await lab(), await J("const { db } = await import('/js/db.js'); const s=(await db.all('scores'))[0]; return [s.pages, (s.pageMap||[]).join(',')]"))
        await J("document.querySelector('#backBtn').click(); await sleep(800);")
        # notebook
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbCreate').click(); await sleep(2500); document.querySelector('#inkDone')?.click(); await sleep(300);")
        print('notebook at', await lab())
        print(await add([F + 'photo.jpg', F + 'vector8.pdf']), '->', await lab())
        await J("document.querySelector('#panel-pages [data-close]').click(); await sleep(1500);")
        await pg.screenshot(path='/home/claude/shots/addpages_nb.png')
        print('nb items', await J("return window.__nbCount()"))
        await J("document.querySelector('#backBtn').click(); await sleep(1200); [...document.querySelectorAll('#grid .card:not(.folder)')].find(c => /Notebook/.test(c.textContent)).click(); await sleep(2500);")
        print('notebook reopened', await lab())
        await J("document.querySelector('#backBtn').click(); await sleep(1000);")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await J("[...document.querySelectorAll('#grid .card:not(.folder)')].find(c => /Notebook/.test(c.textContent)).click(); await sleep(2500);")
        print('notebook after reload', await lab())
        await J("document.querySelector('#backBtn').click(); await sleep(1000); [...document.querySelectorAll('#grid .card:not(.folder)')].find(c => !/Notebook/.test(c.textContent)).click(); await sleep(2500);")
        print('score after reload', await lab(), await J("const { db } = await import('/js/db.js'); const s=(await db.all('scores')).find(x=>!/Notebook/.test(x.title)); const f=await db.get('files', s.fileId); return [s.more && s.more.length, f.data.byteLength]"))
        # turn the page on show, reload, still turned
        await J("document.querySelector('#pgTurn').click(); await sleep(2000);")
        sz = "return [...document.querySelectorAll('#stage .pg')].map(p => Math.round(p.getBoundingClientRect().width) + 'x' + Math.round(p.getBoundingClientRect().height)).join(' ')"
        print('turned', await lab(), await J(sz))
        await pg.screenshot(path='/home/claude/shots/turned.png')
        await J("document.querySelector('#backBtn').click(); await sleep(800);"); await pg.reload(); await pg.wait_for_timeout(2500)
        await J("[...document.querySelectorAll('#grid .card:not(.folder)')].find(c => !/Notebook/.test(c.textContent)).click(); await sleep(3000);")
        print('turned after reload', await lab(), await J(sz))
        # the whole score as a PDF, with the added pages
        async with pg.expect_download() as dl:
            await J("document.querySelector('#exportPdfBtn').click(); await sleep(400); document.querySelector('#expWith').click();")
        d = await dl.value; await d.save_as('/home/claude/shots/withadded.pdf')
        import subprocess; print('pdf pages', subprocess.run(['python3', '-c', "import pypdf;print(len(pypdf.PdfReader('/home/claude/shots/withadded.pdf').pages))"], capture_output=True, text=True).stdout.strip())
        # a page as a picture
        await J("document.querySelector('#nbExportBtn').click(); await sleep(400);")
        print('pic buttons', await J("return [...document.querySelectorAll('#expPics button b')].map(b=>b.textContent)"))
        async with pg.expect_download() as dl:
            await J("document.querySelector('#expPics button').click();")
        d = await dl.value; path = '/home/claude/shots/export_page.jpg'; await d.save_as(path)
        from PIL import Image; im = Image.open(path); print('picture', d.suggested_filename, im.size)
        print('errors', errs[:5]); await b.close()
asyncio.run(main())
