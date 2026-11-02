# The writing tools step aside after writing, and come back with the small pen
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbPapers button[data-v=\"plain\"]').click(); await sleep(300); document.querySelector('#nbCreate').click(); await sleep(2500);")
        await J("document.querySelector('.tour-skip')?.click(); await sleep(300);")
        st = await J("return [document.querySelector('#inkbar').hidden, document.querySelector('#inkbar').classList.contains('away')]")
        # a pen stroke on the page
        await J("""const t = document.querySelector('#stage'); const r = t.getBoundingClientRect(); const x = r.left + r.width * 0.5, y = r.top + r.height * 0.5;
          const ev = (type, dx) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: 'pen', isPrimary: true, clientX: x + dx, clientY: y, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown', 0); for (let k = 1; k < 10; k++) { ev('pointermove', k * 8); await sleep(16); } ev('pointerup', 80);""")
        await pg.wait_for_timeout(1000); mid = await J("return document.querySelector('#inkbar').classList.contains('away')")
        await pg.wait_for_timeout(3500); aw = await J("return [document.querySelector('#inkbar').classList.contains('away'), document.querySelector('#inkTab').hidden]")
        await J("document.querySelector('#inkTab').click(); await sleep(400);")
        back = await J("return [document.querySelector('#inkbar').classList.contains('away'), document.querySelector('#inkTab').hidden]")
        print('start', st, 'after 1 s', mid, 'after 4.5 s', aw, 'after the pen', back)
        print('PASS' if st == [False, False] and mid is False and aw == [True, False] and back == [False, True] else 'FAIL', 'ink tools step aside'); print(errs[:3])
        await b.close()
asyncio.run(main())
