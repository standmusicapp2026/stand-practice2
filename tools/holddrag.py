# Library: holding a score chooses it, and moving then (without lifting) carries it; Compose: a
# window (Layout) closes with Compose
import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf', '/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
        r = await pg.evaluate("""async () => { const sleep = (ms) => new Promise(r => setTimeout(r, ms));
          const card = document.querySelectorAll('#grid .card:not(.folder)')[0], r0 = card.getBoundingClientRect(), x = r0.left + r0.width / 2, y = r0.top + r0.height / 2;
          const ev = (type, xx, yy) => card.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 11, pointerType: 'touch', clientX: xx, clientY: yy, isPrimary: true }));
          ev('pointerdown', x, y); await sleep(750);
          const chosen = document.querySelector('#grid').classList.contains('editing');
          for (let i = 1; i <= 6; i++) { ev('pointermove', x + i * 15, y + i * 10); await sleep(30); }
          const dragging = document.body.classList.contains('lib-dragging');
          window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 11, pointerType: 'touch', clientX: x + 90, clientY: y + 60 })); card.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerId: 11, pointerType: 'touch', clientX: x + 90, clientY: y + 60 }));
          await sleep(300);
          return { chosen, dragging, after: document.body.classList.contains('lib-dragging') }; }""")
        print('library hold then drag:', json.dumps(r))
        r2 = await pg.evaluate("""async () => { const sleep = (ms) => new Promise(r => setTimeout(r, ms));
          const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'T', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(800);
          document.querySelector('[data-panel="cplayout"]').click(); await sleep(300);
          const open = !document.querySelector('#panel-cplayout').hidden;
          document.querySelector('#cpBack').click(); await sleep(800);
          return { open, afterBack: !document.querySelector('#panel-cplayout').hidden, home: !document.querySelector('#library').hidden }; }""")
        print('compose window closes:', json.dumps(r2))
        print('errors', errs[:3]); await b.close()
asyncio.run(main())
