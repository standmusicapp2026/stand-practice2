# A big library: 150 scores. How quick are going home, searching, sorting, opening a folder?
import asyncio, json, time, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.wait_for_timeout(2000)
        comps = ['Bach', 'Brahms', 'Dvořák', 'Elgar', 'Haydn', 'Popper', 'Saint-Saëns', 'Schumann', 'Shostakovich', 'Tchaikovsky']
        await J("const { db } = await import('/js/db.js'); const s0 = (await db.all('scores'))[0]; const C=" + json.dumps(comps) + "; for (let i=0;i<150;i++) { await db.put('scores', { ...s0, id: 'big'+i, title: 'Sonata No. '+(i+1), composer: C[i%10], added: Date.now()-i*1000, opened: Date.now()-i*5000 }); }")
        await pg.reload(); await pg.wait_for_timeout(2500)
        print('cards', await J("return document.querySelectorAll('#grid .card').length"))
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        R = {}
        async def tm(name, act, cond):
            t0 = time.time(); await J(act); await pg.wait_for_function(cond, timeout=30000); R.setdefault(name, []).append(int((time.time()-t0)*1000))
        for k in range(3):
            await tm('open score', f"document.querySelectorAll('#grid .card:not(.folder)')[{k*20}].click()", "document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)")
            await pg.wait_for_timeout(800)
            await tm('back home', "document.querySelector('#backBtn').click()", "!document.querySelector('#library').hidden && document.querySelectorAll('#grid .card').length > 10")
            await pg.wait_for_timeout(800)
        # search box in the library, if there is one
        has = await J("return !!document.querySelector('#libSearch, #search, input[type=search]')")
        if has:
            t0 = time.time()
            await J("const i=document.querySelector('#libSearch, #search, input[type=search]'); i.focus(); for (const ch of 'schu') { i.value += ch; i.dispatchEvent(new Event('input', {bubbles:true})); await sleep(60); }")
            await pg.wait_for_timeout(400)
            R['search 4 letters'] = [int((time.time()-t0)*1000)]
            print('found', await J("return document.querySelectorAll('#grid .card:not(.folder)').length"))
        # long tasks while scrolling
        await J("window.__lt=[]; new PerformanceObserver(l=>{ for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({entryTypes:['longtask']});")
        await J("for (let i=0;i<20;i++){ document.scrollingElement.scrollTop += 300; document.querySelector('#library').scrollTop += 300; await sleep(50); }")
        await pg.wait_for_timeout(1500)
        print('long tasks while scrolling', await J("return window.__lt"))
        for k, v in R.items(): print(f'{k:20s} {v}')
        print('errors', errs[:5]); await b.close()
asyncio.run(main())
