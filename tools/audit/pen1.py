# The Apple Pencil's first stroke on a page (markings closed) writes at once; half-page view shows markings
import asyncio, sys
sys.path.insert(0, '/home/claude/tools/audit')
from base import *
PEN = """
const st = document.querySelector('#stage'), r = document.querySelector('.pg').getBoundingClientRect();
const ev = (type, x, y) => st.dispatchEvent(new PointerEvent(type, { pointerId: 7, pointerType: 'pen', clientX: x, clientY: y, pressure: 0.5, bubbles: true, cancelable: true, isPrimary: true, buttons: type === 'pointerup' ? 0 : 1 }));
const x0 = r.left + r.width * 0.3, y0 = r.top + r.height * 0.4;
ev('pointerdown', x0, y0);
for (let k = 1; k <= 12; k++) { ev('pointermove', x0 + k * 12, y0 + k * 2); await sleep(16); }
ev('pointerup', x0 + 144, y0 + 24);
await sleep(900);
return [document.querySelector('#inkbar').hidden];
"""
async def main():
    async with async_playwright() as p:
        b, pg, errs = await setup(p)
        await J(pg, "document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        print('inkbar hidden after pen', await J(pg, PEN))
        await pg.wait_for_timeout(800)
        print('ink', await J(pg, INKCOUNT))
        # half-page view shows the markings
        await J(pg, "document.querySelector('#inkBtn').click(); await sleep(300);")
        await J(pg, "const S = window.__S; return 0")
        await b.close()
        print([e for e in errs if 'PAGEERR' in e][:5])
asyncio.run(main())
