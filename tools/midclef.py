# A clef change in the middle of a bar: drawn there, kept through MusicXML, set from the clef palette
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1400, 'height': 1000})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""async () => {
          const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const X = await import('/js/compose/musicxml.js');
          await E.createComposition({ insts: ['cello'], time: [4, 4], bars: 3, key: 0 });
          await new Promise((r) => setTimeout(r, 300));
          const C = window.__compose; const st = M.allStaves(C.score)[0];
          const n = (s) => ({ id: M.newId(), t: 4, dots: 0, notes: [{ s, a: 0 }] });
          st.clef = 'tenor';
          st.bars[0] = [n(29), n(28), { ...n(16), clef: 'bass' }, n(15)];
          st.bars[1] = [n(16), n(17), n(18), n(19)];
          st.clefs = { 1: 'bass' };
          window.__composeRelayout();
          const end0 = M.clefEnd(st, 0), at1 = M.clefAt(st, 1), pos2 = M.clefAtPos(C.score, st, 0, 960);
          const xml = X.toMusicXML(C.score);
          const S2 = X.fromMusicXML(xml); const st2 = S2.parts[0].staves[0];
          const back = { clef: st2.clef, ev2: st2.bars[0][2].clef || null, clefs: st2.clefs };
          // the palette: one note selected in the middle of bar 2 gets a tenor clef
          C.sel.clear(); C.sel.add(st.bars[1][2].id); C.selBars = null;
          window.__composeTest.applySig('clef', 'tenor', st, 1, null);
          const pal = { ev: M.allStaves(C.score)[0].bars[1][2].clef, at2: M.clefAt(M.allStaves(C.score)[0], 2), end1: M.clefEnd(M.allStaves(C.score)[0], 1) };
          return { end0, at1, pos2, xmlHas: (xml.match(/<clef>/g) || []).length, back, pal };
        }""")
        print(json.dumps(r), errs)
        await pg.screenshot(path='/home/claude/shots/midclef.png')
        await b.close()
asyncio.run(main())
