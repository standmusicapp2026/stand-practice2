# Compose guitar chord diagrams: every shape holds exactly the notes of its chord (checked string by
# string for 40 chords in all keys and kinds), open shapes where they exist; the button in Text shows
# the diagrams over the chord symbols and makes room for them; a second tap hides them; no errors.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const L = await import('/js/compose/engrave.js'); const S = await import('/js/compose/chordshapes.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        r = await J("""const OPEN = [40, 45, 50, 55, 59, 64], PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
          const KIND = { '': [0, 4, 7], m: [0, 3, 7], 7: [0, 4, 7, 10], m7: [0, 3, 7, 10], maj7: [0, 4, 7, 11], sus4: [0, 5, 7], sus2: [0, 2, 7], m7b5: [0, 3, 6, 10], dim7: [0, 3, 6, 9], 6: [0, 4, 7, 9], m6: [0, 3, 7, 9], dim: [0, 3, 6] };
          const bad = [], none = []; let n = 0;
          for (const root of ['C', 'C#', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']) for (const k of Object.keys(KIND)) {
            const sym = root + k, sh = S.chordShape(sym); if (!sh) { none.push(sym); continue; } n++;
            const pc = (PC[root[0]] + (root[1] === '#' ? 1 : root[1] === 'b' ? -1 : 0) + 12) % 12;
            const want = new Set(KIND[k].map((x) => (x + pc) % 12)), got = sh.frets.map((f, i) => (f < 0 ? null : (OPEN[i] + f) % 12)).filter((x) => x !== null);
            const lowest = sh.frets.findIndex((f) => f >= 0);
            const ok = got.every((x) => want.has(x)) && [...want].every((x) => got.includes(x) || (k === 'm7b5' && false)) && (OPEN[lowest] + sh.frets[lowest]) % 12 === pc && Math.max(...sh.frets) - Math.min(...sh.frets.filter((f) => f > 0)) <= 3;
            if (!ok) bad.push(sym + ' ' + sh.frets.join(','));
          }
          return { n, bad, none: none.length, open: ['C', 'G', 'D', 'Am', 'E', 'Em', 'A7'].map((c) => S.chordShape(c).base === 1 && S.chordShape(c).frets.includes(0)) };""")
        check(r['n'] >= 140 and not r['bad'], f'{r["n"]} shapes, every one exactly its chord, root in the bass, within a hand\\'s reach {r["bad"][:5]}')
        check(all(r['open']), f'open shapes for C, G, D, Am, E, Em, A7 {r["open"]}')
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Chords', insts: ['guitar'], time: [4, 4], bars: 8 }); await sleep(900);
          const st = M.allStaves(C.score)[0]; const ch = ['C', 'Am', 'F', 'G7', 'Bb', 'Bm7', 'Ebmaj7', 'D'];
          for (let m = 0; m < 8; m++) st.bars[m] = [{ id: M.newId(), t: 1, dots: 0, notes: [{ s: 30, a: 0 }], chord: ch[m] }];
          C.mode = 'select'; C.sel.clear(); C.sel.add(st.bars[0][0].id); C.tab = 'text'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(150);""")
        top = lambda: J("const lay = L.layoutScore(C.score); return +lay.pages[0].systems[0].staves[0].y.toFixed(2)")
        y0 = await top()
        await J("document.querySelector('#cpPalBody button[aria-label=\"Guitar chord diagrams\"]').click(); await sleep(200);")
        on = await J("return !!C.score.layout.chordDiagrams"); y1 = await top()
        check(on and y1 > y0 + 3, f'the button shows the diagrams, with room for them over the staff {y0} → {y1}')
        await J("T.renderTab(); await sleep(50); document.querySelector('#cpPalBody button[aria-label=\"Guitar chord diagrams\"]').click(); await sleep(200);")
        off = await J("return !C.score.layout.chordDiagrams"); y2 = await top()
        check(off and abs(y2 - y0) < 0.01, f'tapped again: hidden, the page as before {y2}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose guitar chord diagrams')
asyncio.run(main())
