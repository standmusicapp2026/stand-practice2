import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1024,'height':1366}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' and 'peerjs' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', '/home/claude/fixtures/imslp12.pdf'); await pg.wait_for_timeout(3000)
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J("document.querySelector('[data-panel=\"settings\"]')?.click(); await sleep(300); document.querySelector('#pagesBtn')?.click(); await sleep(800); document.querySelector('#pgGlue').click(); await sleep(2500);")
        await pg.screenshot(path='/home/claude/shots/glue_tool.png')
        await J("[...document.querySelectorAll('.review-top button')].find(b=>/Done|Save|Move/.test(b.textContent))?.click(); await sleep(2500);")
        print(await J("const { db } = await import('/js/db.js'); return (await db.all('scores'))[0].glue"))
        print('label', await J("return document.querySelector('#pageLabel').textContent"))
        await pg.screenshot(path='/home/claude/shots/glue_p1.png')
        await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(2000)
        await pg.screenshot(path='/home/claude/shots/glue_p2.png')
        print('label', await J("return document.querySelector('#pageLabel').textContent"))
        # close and reopen
        await J("document.querySelector('#backBtn').click(); await sleep(800); document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J("const r=document.querySelector('#pageRange'); r.value=1; r.dispatchEvent(new Event('input')); await sleep(1500);")
        await pg.screenshot(path='/home/claude/shots/glue_reopen.png')
        print(errs); await b.close()
asyncio.run(main())
