import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *

async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, vw=1024, vh=1366)
        await J(pg, "document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(600);")
        L, T, W, H = await J(pg, "const r=document.querySelector('.pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];")
        await stroke(pg, L + W*0.3, T + H*0.8, L + W*0.6, T + H*0.82)
        await pg.wait_for_timeout(800)
        await J(pg, "document.querySelector('#inkDone').click(); await sleep(300); const h=document.querySelector('#halfTurn'); h.checked=true; h.dispatchEvent(new Event('change')); await sleep(300);")
        print('before', await J(pg, "return [document.querySelectorAll('#stage canvas.ink').length, document.querySelector('#pageLabel').textContent]"))
        await pg.mouse.click(1000, 700)
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/half.png')
        print('half view', await J(pg, "return [document.querySelectorAll('#stage canvas.ink').length, document.querySelector('#pageLabel').textContent, document.querySelectorAll('.half-clip').length]"))
        # try the pen in half view: markings button
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(800);")
        print('after ink on', await J(pg, "return [document.querySelectorAll('#stage canvas.ink').length, document.querySelector('#pageLabel').textContent]"))
        print(errs[:10])
        await b.close()
asyncio.run(main())
