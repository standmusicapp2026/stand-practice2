import asyncio
from playwright.async_api import async_playwright
D='/home/claude/fixtures/titles/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        toasts=[]
        await pg.evaluate("() => { const t=document.querySelector('#toast'); new MutationObserver(()=>{ (window.__T=window.__T||[]).push(t.textContent) }).observe(t,{childList:true,subtree:true,characterData:true}); }")
        files=[D+f for f in ['a.pdf','b.pdf','broken.pdf','c.pdf','d.pdf','notes.txt','Elgar_-_Cello_Concerto_in_E_minor.pdf']]
        await pg.set_input_files('#importInput', files)
        await pg.wait_for_timeout(9000)
        print('toasts', await pg.evaluate("() => [...new Set(window.__T||[])]"))
        print(await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('scores')).map(s=>s.title+' | '+s.composer) }"))
        print('errors', errs)
        await b.close()
asyncio.run(main())
