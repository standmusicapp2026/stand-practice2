import asyncio, json, sys
from playwright.async_api import async_playwright

URL = 'http://127.0.0.1:' + __import__('os').environ.get('PORT','8766') + '/index.html'

async def setup(p, pdf='/home/claude/fixtures/vector8.pdf', vw=1366, vh=1024):
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, has_touch=True)
    pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
    errs = []
    pg.on('pageerror', lambda e: errs.append('PAGEERR ' + str(e)))
    pg.on('console', lambda m: errs.append(m.type + ' ' + m.text) if m.type in ('error', 'warning') else None)
    await pg.goto(URL); await pg.wait_for_timeout(1500)
    await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }")
    await pg.wait_for_timeout(700)
    await pg.set_input_files('#importInput', [pdf])
    await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
    await pg.wait_for_timeout(500)
    return b, pg, errs

def J(pg, js):
    return pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")

INKCOUNT = """
const d = await new Promise((r)=>{const q=indexedDB.open('stand'); q.onsuccess=()=>r(q.result);});
const all = await new Promise((r)=>{const q=d.transaction('ink').objectStore('ink').getAll(); q.onsuccess=()=>r(q.result);});
return all.map(x=>[x.key, x.items.length, x.items.map(i=>i.t+(i.p?("@y"+i.p[0][1].toFixed(2)):"")).join(",")]);
"""

async def stroke(pg, x0, y0, x1, y1, steps=12):
    await pg.mouse.move(x0, y0); await pg.mouse.down()
    for k in range(1, steps + 1):
        await pg.mouse.move(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)
    await pg.mouse.up()
