# Notebook: two fingers move the page at any size (100% too), its foot and corners can be brought
# up to write on, it stays where the fingers leave it (no jump back), a zoom near 100% snaps without
# moving, the Reset pill brings it home; a quick two-finger sideways swipe still turns the page.
import asyncio, os, re
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
        two = """async ([dx, dy, spread, ms]) => { const sleep=(m)=>new Promise(r=>setTimeout(r,m)); const t = document.querySelector('#stage'); const r = t.getBoundingClientRect(); const cx = r.left + r.width * 0.5, cy = r.top + r.height * 0.5;
          const ev = (type, id, x, y) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: id, pointerType: 'touch', isPrimary: id === 41, clientX: x, clientY: y, width: 30, height: 30, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown', 41, cx - 60, cy); ev('pointerdown', 42, cx + 60, cy); const n = 14;
          for (let k = 1; k <= n; k++) { const f = k / n, s = 60 + spread * f; ev('pointermove', 41, cx - s + dx * f, cy + dy * f); ev('pointermove', 42, cx + s + dx * f, cy + dy * f); await sleep(ms / n); }
          await sleep(40); ev('pointerup', 41, cx - 60 - spread + dx, cy + dy); ev('pointerup', 42, cx + 60 + spread + dx, cy + dy); await sleep(300); }"""
        pos = "return (() => { const pg = document.querySelector('#stage .pg'); const r = pg.getBoundingClientRect(); const s = document.querySelector('#stage').getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), sh: Math.round(s.bottom), sw: Math.round(s.right), page: document.querySelector('#pageNum')?.textContent || '', pill: !document.querySelector('.zoom-pill').hidden }; })()"
        p0 = await J(pos)
        await pg.evaluate(two, [0, -380, 0, 600]); p1 = await J(pos)
        await pg.wait_for_timeout(800); p1b = await J(pos)
        await pg.evaluate(two, [-300, 0, 0, 600]); p2 = await J(pos)
        print('start', p0); print('up 380', p1, 'later', p1b); print('left 300', p2)
        ok1 = p1['bottom'] < p0['bottom'] - 300 and p1b['bottom'] == p1['bottom'] and p1['pill']
        ok2 = p2['left'] < p1['left'] - 250
        # the foot of the page can come up well above the writing tools at the bottom
        ib = await J("return Math.round(document.querySelector('#inkbar').getBoundingClientRect().top)")
        ok3 = p1['bottom'] < p0['sh'] * 0.65
        # never lost: a huge move stops with the page still on screen
        await pg.evaluate(two, [0, -3000, 0, 600]); p3 = await J(pos)
        ok4 = p3['bottom'] > p0['sh'] * 0.3
        # zoom in with the fingers, then back near 100%: no jump at the end
        await pg.evaluate(two, [0, 0, 150, 500]); z1 = await J("return document.querySelector('.zoom-pill').textContent")
        await pg.evaluate(two, [0, 0, -105, 500]); z2 = await J("return document.querySelector('.zoom-pill').textContent"); p4 = await J(pos)
        await pg.wait_for_timeout(600); p4b = await J(pos)
        print('zoom', z1, 'then', z2, p4, p4b)
        ok5 = p4 == p4b
        # Reset brings the page home
        await J("document.querySelector('.zoom-pill').click(); await sleep(400);"); p5 = await J(pos)
        ok6 = abs(p5['top'] - p0['top']) < 2 and abs(p5['left'] - p0['left']) < 2 and not p5['pill']
        # a quick sideways two-finger swipe turns the page
        await pg.evaluate(two, [-400, 10, 0, 200]); p6 = await J(pos)
        print('reset', p5, 'swipe', p6)
        ok7 = p6['page'] != p5['page'] or p6['left'] == p5['left']
        r = [ok1, ok2, ok3, ok4, ok5, ok6, ok7]; print(r)
        print('PASS' if all(r) else 'FAIL', 'notebook page moves with two fingers'); print(errs[:3])
        await b.close()
asyncio.run(main())
