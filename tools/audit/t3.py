import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *
SC = """
const d = await new Promise((r)=>{const q=indexedDB.open('stand'); q.onsuccess=()=>r(q.result);});
const g = (s)=>new Promise((r)=>{const q=d.transaction(s).objectStore(s).getAll(); q.onsuccess=()=>r(q.result);});
const sc = await g('scores'), f = await g('files');
return [sc.map(s=>s.id+':'+s.title+(s.preview?' preview':'')), f.map(x=>x.id), (await g('ink')).map(x=>x.key)];
"""
async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, vw=1024, vh=1366)
        await J(pg, "document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(600);")
        L, T, W, H = await J(pg, "const r=document.querySelector('.pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];")
        await stroke(pg, L + W*0.3, T + H*0.5, L + W*0.6, T + H*0.52)
        await J(pg, "document.querySelector('#inkDone').click(); const b=document.querySelector('#score [data-panel=\"settings\"]'); b.click(); await sleep(200); document.querySelector('#delScore').click(); await sleep(100); document.querySelector('#delScoreYes').click(); await sleep(400);")
        print('right after delete', await J(pg, SC), await J(pg, "return document.querySelectorAll('#grid .card:not(.folder)').length"))
        await pg.wait_for_timeout(3500)
        print('3.5s later', await J(pg, SC))
        await pg.reload(); await pg.wait_for_timeout(2000)
        print('after reload cards', await J(pg, "return [...document.querySelectorAll('#grid .card:not(.folder) .ttl')].map(x=>x.textContent)"))
        await J(pg, "document.querySelector('#grid .card:not(.folder)')?.click(); await sleep(1500);")
        print('toast', await J(pg, "return document.querySelector('#toast').textContent"))
        print(errs[:10])
        await b.close()
asyncio.run(main())
