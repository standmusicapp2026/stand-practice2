# The writing tools: in a notebook they always stay; on a score they step aside 10 s after writing,
# come back with the small pen, and a finger tap in the middle shows or hides them
import asyncio, os
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        stroke = """const t = document.querySelector('#stage'); const r = t.getBoundingClientRect(); const x = r.left + r.width * 0.5, y = r.top + r.height * 0.45;
          const ev = (type, dx) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: 'pen', isPrimary: true, clientX: x + dx, clientY: y, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown', 0); for (let k = 1; k < 10; k++) { ev('pointermove', k * 8); await sleep(16); } ev('pointerup', 80);"""
        state = "return [document.querySelector('#inkbar').hidden, document.querySelector('#inkbar').classList.contains('away'), document.querySelector('#inkTab').hidden]"
        res = []
        # ---- notebook: always there
        await J("document.querySelector('#newNotebookBtn').click(); await sleep(1500); document.querySelector('#nbPapers button[data-v=\"plain\"]').click(); await sleep(300); document.querySelector('#nbCreate').click(); await sleep(2500);")
        await J("document.querySelector('.tour-skip')?.click(); await sleep(300);")
        st = await J(state)
        await J(stroke)
        await pg.wait_for_timeout(11000); nb = await J(state)
        print('notebook start', st, 'after 11 s', nb)
        res.append(st[:2] == [False, False] and nb[:2] == [False, False])
        await J("document.querySelector('#backBtn').click(); await sleep(1200);")
        # ---- a score
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("[...document.querySelectorAll('#grid .card:not(.folder) .ttl')].some(t => t.textContent.includes('Cello'))", timeout=60000)
        await J("[...document.querySelectorAll('#grid .card:not(.folder)')].find(c => c.querySelector('.ttl').textContent.includes('Cello')).click(); await sleep(2500);")
        await J("document.querySelector('#inkBtn').click(); await sleep(500);")
        await J(stroke)
        await pg.wait_for_timeout(4500); s1 = await J(state)
        await pg.wait_for_timeout(6500); s2 = await J(state)
        await J("document.querySelector('#inkTab').click(); await sleep(400);")
        s3 = await J(state)
        # a finger tap in the middle: away, then back
        tap = """const t = document.querySelector('#stage'); const r = t.getBoundingClientRect(); const x = r.left + r.width * 0.5, y = r.top + r.height * 0.55;
          const ev = (type) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 31, pointerType: 'touch', isPrimary: true, clientX: x, clientY: y, width: 30, height: 30, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown'); await sleep(60); ev('pointerup'); await sleep(450);"""
        await pg.wait_for_timeout(700)
        await J(tap); s4 = await J(state)
        await J(tap); s5 = await J(state)
        print('score after 4.5 s', s1, 'after 11 s', s2, 'pen', s3, 'tap', s4, 'tap again', s5)
        res.append(s1[1] is False and s2[1] is True and s2[2] is False and s3[1] is False and s4[1] is True and s5[1] is False)
        print('PASS' if all(res) else 'FAIL', 'ink tools: stay in notebooks; on scores step aside after 10 s, the pen and a middle tap bring them back'); print(errs[:3])
        await b.close()
asyncio.run(main())
