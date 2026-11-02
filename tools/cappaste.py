import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        r = await pg.evaluate("""async () => {
          const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
          await E.createComposition({ insts: ['violin', 'piano'], time: [4, 4], bars: 3 }); await new Promise(r => setTimeout(r, 600));
          const C = window.__compose;
          const N = (p, t = 4) => ({ t, dots: 0, ps: [p], acc: {}, art: [] });
          C.capture = { bars: Array.from({ length: 8 }, (_, i) => [N(i % 5), N(1), N(2), N(3)]), clef: 'treble', key: 0, time: [4, 4] };
          document.querySelector('#capTo').value = '';
          const st = C.score.parts[0].staves[0];
          window.__composeTest.pasteCapture(st, 2);
          const S = C.score;
          return { bars: S.measures.length, filled: st.bars.map((b) => b.filter((e) => !e.rest).length).join(''), others: M.allStaves(S).map((s) => s.bars.length), final: S.measures.map((m, i) => m.bar ? i + m.bar : '').filter(Boolean) };
        }""")
        print(r); print(errs); await b.close()
asyncio.run(main())
