# Notebook: a finger (60 px wide, as on an iPad) swipes the page over with the markings bar open;
# with finger writing on, the same swipe draws instead and the page stays.
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width':1366,'height':1024}, has_touch=True); pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("""document.querySelector('#newNotebookBtn').click(); await sleep(1500);
          document.querySelector('#nbHasCover').checked=false; document.querySelector('#nbHasCover').dispatchEvent(new Event('change'));
          document.querySelector('#nbPapers button[data-v="plain"]').click(); await sleep(300);
          document.querySelector('#nbCreate').click(); await sleep(2500);""")
        swipe = """const st = document.querySelector('#stage'); const ev = (type, x) => (type === 'pointerdown' ? st : window).dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 21, pointerType: 'touch', clientX: x, clientY: 500, width: 60, height: 60, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
          const lbl = () => (document.querySelector('#pageLabel') || {}).textContent;
          const strokes = () => window.__inkCount ? window.__inkCount() : document.querySelectorAll('#stage canvas').length;
          const b0 = lbl(); ev('pointerdown', 900); for (let i = 1; i <= 8; i++) { ev('pointermove', 900 - i * 50); await sleep(16); } ev('pointerup', 500); await sleep(900);
          return [b0, lbl()];"""

        # two pages to swipe between
        await J("document.querySelector('#inkInsert')?.click(); await sleep(400); document.querySelector('#insTabs [data-v=\"pages\"]')?.click(); await sleep(400);")
        await J("const b=[...document.querySelectorAll('#panel-insert button, .ins-page')].find(x=>/blank|page/i.test(x.textContent)); if (b) b.click(); await sleep(1200); document.querySelector('.panel-close, #insClose')?.click(); await sleep(400);")
        await J("for (let i = 0; i < 3; i++) { await window.__nbAddPage?.(); } await sleep(500);")
        print('pages', await J("return window.__nbCount ? window.__nbCount() : null"))
        await J("if (!document.querySelector('#stage').classList.contains('inking')) document.querySelector('#inkBtn').click(); await sleep(400);")
        print('inking?', await J("return document.querySelector('#stage').classList.contains('inking')"))
        print('finger off, swipe:', await J(swipe))
        await J("document.querySelector('#fingerBtn').click(); await sleep(300);")
        await J("document.querySelector('#nbExportBtn') && 0; ")
        print('finger on, swipe:', await J(swipe))
        print('dbg', await J("return window.__dbgDown"))
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/nbf1.png')
        await J("const st = document.querySelector('#stage'); const ev = (type, x) => (type === 'pointerdown' ? st : window).dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 22, pointerType: 'touch', clientX: x, clientY: 300, width: 60, height: 60, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 })); ev('pointerdown', 450); for (let i = 1; i <= 10; i++) { ev('pointermove', 450 + i * 30); await sleep(16); } ev('pointerup', 750); await sleep(600);")
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/nbf.png')
        print(errs[:3]); await b.close()
asyncio.run(main())
