import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *
async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p, vw=1024, vh=1366)
        await J(pg, "document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(600); document.querySelector('.ink-tool[data-tool=\"note\"]').click(); await sleep(300);")
        L, T, W, H = await J(pg, "const r=document.querySelector('.pg').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];")
        await pg.mouse.click(L + W*0.4, T + H*0.4)
        await pg.wait_for_timeout(400)
        print('focused', await J(pg, "return document.activeElement.className"))
        await pg.keyboard.type('Bow change here', delay=30)
        # keyboard appears: same width, less height
        await pg.set_viewport_size({'width': 1024, 'height': 900})
        await pg.wait_for_timeout(600)
        print('after kb resize: focused', await J(pg, "return [document.activeElement.className, document.querySelector('.snote textarea')?.value, document.querySelector('.snote')?.className]"))
        await pg.keyboard.type(' and more', delay=30)
        await pg.wait_for_timeout(1500)
        print('ink', await J(pg, INKCOUNT.replace("i.t+(i.p?(\"@y\"+i.p[0][1].toFixed(2)):\"\")", "i.t+':'+(i.txt||'')")))
        print(errs[:10])
        await b.close()
asyncio.run(main())
