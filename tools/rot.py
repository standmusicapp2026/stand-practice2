import asyncio, math
from playwright.async_api import async_playwright
IMG='/home/claude/s24/Payload/Stand.app/www/covers/29.jpg'
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
        await J("document.querySelector('#inkInsert').click(); await sleep(300); document.querySelector('#insTabs [data-v=\"photos\"]')?.click(); await sleep(200);")
        await pg.set_input_files('#insFile', IMG); await pg.wait_for_timeout(1800)
        rh = await J("const h=document.querySelector('.sel-rot'); const r=h.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]")
        box = await J("const r=document.querySelector('.sel-box').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]")
        cx, cy = box; R = math.hypot(rh[0]-cx, rh[1]-cy)
        await pg.mouse.move(*rh); await pg.mouse.down()
        for k in range(1, 31):
            a = -math.pi/2 + k*(math.pi*0.9/30)
            await pg.mouse.move(cx + R*math.cos(a), cy + R*math.sin(a))
            if k == 15: await pg.screenshot(path='/home/claude/shots/rot_mid.png')
        await pg.mouse.up(); await pg.wait_for_timeout(500)
        print('rot', await J("const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.flatMap(r=>r.items).filter(i=>i.t==='img').map(i=>i.rot)"))
        await pg.screenshot(path='/home/claude/shots/rot_end.png')
        print(errs); await b.close()
asyncio.run(main())
