import asyncio
from playwright.async_api import async_playwright
exec(open('smoke.py').read().split('async def main')[0])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.set_input_files('#importInput', FIX + 'vector8.pdf'); await pg.wait_for_timeout(3000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(2500)
        await pg.evaluate("() => document.querySelector('#inkBtn').click()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => {const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height]}")
        print(r, await pg.evaluate("() => document.elementFromPoint(%d,%d).className" % (r[0]+100, r[1]+200)))
        await pg.evaluate(PEN, [[r[0]+100+i*10, r[1]+200+i*2] for i in range(20)]); await pg.wait_for_timeout(1500)
        print(await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('ink')).map(r=>[r.key, r.items.length]) }"))
        await pg.screenshot(path='/home/claude/shots/dbgpen.png')
        await b.close()
asyncio.run(main())
