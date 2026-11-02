import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *

async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, vw=1024, vh=1366)
        await J(pg, "document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(600);")
        r = await J(pg, "const r=document.querySelector('.pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];")
        print('page', r)
        L, T, W, H = r
        # stroke 1, then a layout (resize) right away
        await stroke(pg, L + W*0.3, T + H*0.3, L + W*0.6, T + H*0.32)
        await J(pg, "window.dispatchEvent(new Event('resize')); await sleep(1500);")
        print('after resize', await J(pg, INKCOUNT))
        vis = await J(pg, "const c=document.querySelector('canvas.ink'); const g=c.getContext('2d'); const d=g.getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=4) if(d[i]) n++; return n;")
        print('ink pixels on new layer', vis)
        await stroke(pg, L + W*0.3, T + H*0.5, L + W*0.6, T + H*0.52)
        await pg.wait_for_timeout(1200)
        print('after stroke2', await J(pg, INKCOUNT))
        print(errs[:10])
        await b.close()
asyncio.run(main())
