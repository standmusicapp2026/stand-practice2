# Layers: write in a named layer, hide it, undo, erase, delete; and how a passage looks
import asyncio, json
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
PEN = open('/home/claude/tools/smoke.py').read().split("PEN = '''")[1].split("'''")[0]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'peerjs' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>{ document.querySelector('.tour-skip')?.click(); }, 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await J("document.querySelector('#grid .card:not(.folder)').click()")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)", timeout=20000)
        await pg.wait_for_timeout(1500); await J("document.querySelector('#inkBtn').click(); await sleep(400);"); print('inking', await J("return !document.querySelector('#inkbar').hidden"))
        r = await J("const r=document.querySelector('#stage .pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height]")
        print('at', await J(f"const e=document.elementFromPoint({r[0]+100},{r[1]+200}); return e.tagName+'.'+e.className+' #'+e.id"))
        await pg.evaluate(PEN, [[r[0]+100+i*10, r[1]+200+i*2] for i in range(20)]); await pg.wait_for_timeout(900)
        print('first', await J("const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.map(r=>r.key+':'+r.items.length)"), await J("return document.querySelector('#inkHint').textContent"))
        await J("document.querySelector('#layerBtn').click(); await sleep(200); document.querySelector('#lyName').value='Paulo performance'; document.querySelector('#lyAdd').click(); await sleep(400);")
        print('chip', await J("return [document.querySelector('#lyChip').hidden, document.querySelector('#lyChip').textContent]"))
        await pg.evaluate(PEN, [[r[0]+100+i*10, r[1]+300+i*2] for i in range(20)]); await pg.wait_for_timeout(500)
        await pg.evaluate(PEN, [[r[0]+100+i*10, r[1]+400] for i in range(20)]); await pg.wait_for_timeout(800)
        cnt = "const { db } = await import('/js/db.js'); const all = await db.all('ink'); return all.flatMap(r=>r.items).map(x=>x.ly||'-').join(',')"
        print('items', await J(cnt))
        await J("document.querySelector('#layerBtn').click(); await sleep(200);")
        await pg.screenshot(path='/home/claude/shots/ly_pop.png')
        print('rows', await J("return [...document.querySelectorAll('.ly-row')].map(r=>r.className+':'+r.textContent)"))
        # hide Paulo
        await J("document.querySelectorAll('.ly-row')[1].querySelector('.ly-eye').click(); await sleep(300);")
        print('after hide rows', await J("return [...document.querySelectorAll('.ly-row')].map(r=>r.className)"), 'chip hidden', await J("return document.querySelector('#lyChip').hidden"))
        await J("document.querySelector('#layerBtn').click(); await sleep(200);")
        await pg.screenshot(path='/home/claude/shots/ly_hidden.png')
        # erase across all strokes with the eraser: hidden stay
        await J("document.querySelector('.ink-tool[data-tool=\"eraser\"]').click(); await sleep(200); document.querySelector('#eraserPop').hidden=true;")
        for y in (200, 300, 400):
            await pg.evaluate(PEN, [[r[0]+80+i*12, r[1]+y+i*0.5] for i in range(25)]); await pg.wait_for_timeout(300)
        await pg.wait_for_timeout(600)
        print('after erase', await J(cnt))
        # undo erase, then show again
        await J("document.querySelector('#inkUndo').click(); await sleep(200); document.querySelector('#inkUndo').click(); await sleep(200); document.querySelector('#inkUndo').click(); await sleep(500);")
        print('after undo', await J(cnt))
        await J("document.querySelector('#layerBtn').click(); await sleep(200); document.querySelectorAll('.ly-row')[1].querySelector('.ly-eye').click(); await sleep(300); document.querySelector('#layerBtn').click();")
        await pg.screenshot(path='/home/claude/shots/ly_shown.png')
        # leave and come back: hidden persists
        await J("document.querySelector('#layerBtn').click(); await sleep(150); document.querySelectorAll('.ly-row')[1].querySelector('.ly-eye').click(); await sleep(200); document.querySelector('#inkDone').click(); await sleep(200); document.querySelector('#backBtn').click(); await sleep(800); document.querySelector('#grid .card:not(.folder)').click(); await sleep(2000);")
        px = await J("const c=document.querySelector('#stage .pg canvas.ink'); const g=c.getContext('2d'); const d=g.getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n")
        print('ink pixels after reopen (only own stroke)', px)
        # delete layer
        await J("document.querySelector('#inkBtn').click(); await sleep(300); document.querySelector('#layerBtn').click(); await sleep(200); document.querySelectorAll('.ly-row')[1].querySelector('.ly-del').click(); await sleep(300); document.querySelector('.ask .danger-fill').click(); await sleep(800);")
        print('after delete', await J(cnt), await J("return document.querySelectorAll('.ly-row').length"))
        # passage look
        await J("const { db } = await import('/js/db.js'); const all = await db.all('ink'); const r0 = all[0]; r0.items.push({t:'passage', kind:'technical', name:'Bars 12–16', x0:0.1,y0:0.3,x1:0.7,y1:0.42, pid:'p1'}); await db.put('ink', r0); document.querySelector('#inkDone').click(); document.querySelector('#backBtn').click(); await sleep(800); document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await pg.screenshot(path='/home/claude/shots/passage_look.png')
        print('errors', errs); await b.close()
asyncio.run(main())
