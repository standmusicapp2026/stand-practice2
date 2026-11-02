import asyncio
from playwright.async_api import async_playwright
S='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/lay'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("""document.querySelector('#newNotebookBtn').click(); await sleep(1500);
          document.querySelector('#nbHasCover').checked=false; document.querySelector('#nbHasCover').dispatchEvent(new Event('change'));
          document.querySelector('#nbPapers button[data-v="plain"]').click(); await sleep(300);
          document.querySelector('#nbCreate').click(); await sleep(2500);""")
        await J("document.querySelector('#inkInsert').click(); await sleep(300); document.querySelector('#insTabs [data-v=\"layouts\"]').click(); await sleep(800);")
        await pg.screenshot(path=S+'/ui_concert.png')
        print(await J("return [...document.querySelectorAll('#insLayouts .ins-layout')].filter(b=>!b.hidden).map(b=>b.textContent)"))
        await J("[...document.querySelectorAll('.lay-cats button')].find(b=>b.textContent==='Career').click(); await sleep(300);")
        print(await J("return [...document.querySelectorAll('#insLayouts .ins-layout')].filter(b=>!b.hidden).map(b=>b.textContent)"))
        await pg.screenshot(path=S+'/ui_career.png')
        n0 = await J("return document.querySelector('#scrubLabel')?.textContent || ''")
        await J("[...document.querySelectorAll('.lay-cats button')].find(b=>b.textContent==='Concerts').click(); await sleep(200); [...document.querySelectorAll('#insLayouts .ins-layout')].find(b=>b.textContent==='Programme, 3 columns').click(); await sleep(2500);")
        print('pages', await J("return [window.__nbCount(), document.querySelectorAll('#stage .pgi').length]"))
        await pg.screenshot(path=S+'/ui_land.png')
        await J("document.querySelector('#nbExportBtn').click(); await sleep(500);")
        print('export', await J("return [...document.querySelectorAll('#expPages button')].map(b=>b.textContent)"))
        await pg.screenshot(path=S+'/ui_export.png')
        print(errs); await b.close()
asyncio.run(main())
