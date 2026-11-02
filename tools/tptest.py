import asyncio, json
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
          const out = {};
          const setup = async (insts, key) => {
            await E.createComposition({ insts, time: [4, 4], bars: 4, key }); await new Promise(r => setTimeout(r, 500));
            const C = window.__compose; let id = 1;
            const N = (name) => { const L = 'CDEFGAB'.indexOf(name[0]); const a = name.includes('#') ? 1 : name.includes('b') && name.length > 2 ? -1 : 0; const o = +name[name.length - 1]; return { id: 'x' + (id++), t: 4, dots: 0, notes: [{ s: o * 7 + L, a }] }; };
            for (const st of M.allStaves(C.score)) { st.bars[0] = ['C4', 'E4', 'F#4', 'Bb4'].map(N); st.bars[1] = ['G4', 'B4', 'D5', 'C5'].map(N); st.bars[2] = ['C4', 'C4', 'C4', 'C4'].map(N); }
            C.score.measures[2].key = -1;  // a key change at bar 3 (F major)
            window.__composeRelayout(); return C;
          };
          const names = (C, st, m) => st.bars[m].map((e) => e.notes ? e.notes.map((n) => M.noteName(n.s, n.a)).join('+') : 'r').join(' ');
          const keys = (C) => C.score.measures.slice(0, 4).map((x, i) => M.keyAt(C.score, i));
          const T = () => window.__composeTest;
          // 1. whole score up a tone
          let C = await setup(['violin'], 0); let st = M.allStaves(C.score)[0];
          T().transpose(1, 2);
          out.wholeTone = { keys: keys(C), b1: names(C, st, 0), b2: names(C, st, 1), b3: names(C, st, 2) };
          // 2. whole score to E flat major
          C = await setup(['violin'], 0); st = M.allStaves(C.score)[0];
          T().transposeToKey(0, -3);
          out.toEb = { keys: keys(C), b1: names(C, st, 0), b3: names(C, st, 2) };
          // 3. bar 2 only, in a 2-instrument score, only the first staff selected: key stays
          C = await setup(['violin', 'cello'], 0); const [s1, s2] = M.allStaves(C.score);
          T().selectBars(s1, s1, 1, 1);
          T().transpose(4, 7);
          out.barOnly = { keys: keys(C), v_b1: names(C, s1, 0), v_b2: names(C, s1, 1), c_b2: names(C, s2, 1) };
          // 4. down an octave whole score
          C = await setup(['violin'], 0); st = M.allStaves(C.score)[0]; C.selBars = null;
          T().transpose(-7, -12);
          out.octDown = { keys: keys(C), b1: names(C, st, 0) };
          // 5. Gb major up a semitone -> G major
          C = await setup(['violin'], -6); st = M.allStaves(C.score)[0]; C.score.measures[2].key = null;
          T().transpose(1, 1);
          out.GbUp = { keys: keys(C), b1: names(C, st, 0) };
          // 6. clarinet (written key differs) whole score up a tone
          C = await setup(['clarinet'], 0); st = M.allStaves(C.score)[0];
          T().transpose(1, 2);
          out.clar = { keys: keys(C), b1: names(C, st, 0) };
          // 7. undo
          document.querySelector('#cpUndo')?.click(); await new Promise(r => setTimeout(r, 200));
          out.undo = names(C, M.allStaves(C.score)[0], 0);
          return out;
        }""")
        for k, v in r.items(): print(k, v)
        print(errs); await b.close()
asyncio.run(main())
