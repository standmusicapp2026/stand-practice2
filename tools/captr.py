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
          await E.createComposition({ insts: ['cello'], time: [4, 4], bars: 6, key: -1 }); await new Promise(r => setTimeout(r, 600));
          const C = window.__compose;
          // treble clef, C major, 3/4: C D E F | G A B C
          const N = (p, t = 4) => ({ t, dots: 0, ps: [p], acc: {}, art: [] });
          C.capture = { bars: [[N(-2), N(-1), N(0)], [N(1), N(2), N(3)]], clef: 'treble', key: 0, time: [3, 4] };
          const out = {};
          for (const to of ['', '2', '-3']) {
            document.querySelector('#capTo').value = to;
            const st = C.score.parts[0].staves[0];
            window.__composeTest.pasteCapture(st, 0);
            out[to || 'same'] = { key: M.keyAt(C.score, 0), time: M.timeAt(C.score, 0), clef: M.clefAt(st, 0), notes: st.bars.slice(0, 2).flat().map(e => e.notes ? M.noteName(e.notes[0].s, e.notes[0].a) : 'r').join(' '), after: { key: M.keyAt(C.score, 2), time: M.timeAt(C.score, 2), clef: M.clefAt(st, 2) } };
          }
          return out;
        }""")
        for k, v in r.items(): print(k, v)
        print(errs); await b.close()
asyncio.run(main())
