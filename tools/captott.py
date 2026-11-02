# Pasting captured music with an octave line: the notes go in at the pitch they sound, under an 8va line
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
          await E.createComposition({ insts: ['flute'], time: [3, 4], bars: 4, key: 0 }); await new Promise(r => setTimeout(r, 600));
          const C = window.__compose;
          const N = (p, ott) => ({ t: 4, dots: 0, ps: [p], acc: {}, art: [], ...(ott ? { ott } : {}) });
          C.capture = { bars: [[N(0), N(2, 1), N(4, 1)], [N(6, 1), N(4), { rest: true, t: 4 }]], clef: 'treble', key: 0, time: [3, 4] };
          document.querySelector('#capTo').value = '';
          const st = C.score.parts[0].staves[0];
          window.__composeTest.pasteCapture(st, 0);
          return { notes: st.bars.slice(0, 2).flat().map(e => e.notes ? M.noteName(e.notes[0].s, e.notes[0].a) + M.octaveOf?.(e.notes[0].s) : 'r').join(' '), ss: st.bars.slice(0, 2).flat().map(e => e.notes ? e.notes[0].s : null), spans: (C.score.spans || []).filter(q => q.kind.startsWith('8')).map(q => [q.kind, q.a, q.b]) };
        }""")
        print(r); print(errs); await b.close()
asyncio.run(main())
