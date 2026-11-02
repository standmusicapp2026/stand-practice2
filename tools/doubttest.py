# Captured bars that did not add up are marked to check; changing such a bar clears its mark.
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1400, 'height': 1000})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""async () => {
          const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          await E.createComposition({ insts: ['cello'], time: [4, 4], bars: 4, key: 0 });
          await new Promise((r) => setTimeout(r, 300));
          const C = window.__compose;
          const n = (p, t) => ({ ps: [p], t, dots: 0 });
          C.capture = { clef: 'bass', key: 0, time: [4, 4], bars: [[n(4, 4), n(5, 4), n(6, 4), n(7, 4)], [n(4, 4), n(5, 4), n(6, 4)]], doubt: [false, true], changes: [] };
          const st = M.allStaves(C.score)[0];
          window.__composeTest.pasteCapture(st, 0);
          const marked = C.capDoubt ? [...C.capDoubt.bars.keys()] : [];
          // change the marked bar: select it and transpose it a step
          window.__composeTest.selectBars(st, st, 1, 1);
          window.__composeTest.moveNotes(1);
          const after = C.capDoubt ? [...C.capDoubt.bars.keys()] : [];
          return { marked, after };
        }""")
        print(r, errs)
        await b.close()
asyncio.run(main())
