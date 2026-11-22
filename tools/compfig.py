# Compose figured bass: typed under the notes in Text › Figured bass (top figure first; # b n for
# sharp, flat, natural), drawn stacked under the staff, removed alone, kept through MusicXML and read
# from other programs' files; no errors.
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
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const X = await import('/js/compose/musicxml.js'); const L = await import('/js/compose/engrave.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Continuo', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(900);
          const info = M.staffInfo(C.score); const tg = (x, m, t, p) => ({ staff: { st: x.st, inst: x.inst }, meas: { m }, t, p });
          C.tool.dur = 4; C.tool.dots = 0; for (let i = 0; i < 4; i++) T.commitWrite(tg(info[0], 0, i * 480, i));
          C.undo = []; C.mode = 'select'; const st = M.allStaves(C.score)[0]; C.sel.clear(); C.sel.add(st.bars[0][0].id);
          C.tab = 'text'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(100);""")
        for w in ['6', '6 4', '7 #', 'b5']:
            inp = pg.locator('#cpPalBody input[aria-label="Figured bass"]')
            await inp.fill(w); await inp.press('Enter'); await pg.wait_for_timeout(60)
        r = await J("const st = M.allStaves(C.score)[0]; return st.bars[0].map((e) => e.fig || '')")
        check(r == ['6', '6 4', '7 #', 'b5'], f'figures typed under four notes {r}')
        r = await J("""const lay = L.layoutScore(C.score); const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4); const hit = L.drawPage(g, lay, 0);
          const fm = hit.marks.filter((m) => m.kind === 'fig'); const sy = hit.staves[0].y; return { n: fm.length, below: fm.every((m) => m.y0 > sy + 4), tall: fm.map((m) => +(m.y1 - m.y0).toFixed(1)), rows: M.figRows('7 #') };""")
        check(r['n'] == 4 and r['below'], f'drawn under the staff {r}')
        check(r['tall'][1] > r['tall'][0] and r['rows'] == ['7', '♯'], f'stacked, with real sharps and flats {r}')
        r = await J("""const st = M.allStaves(C.score)[0]; const ev = st.bars[0][1]; C.sel.clear(); C.markSel = { id: ev.id, kind: 'fig', name: ev.fig, m: 0 }; T.syncSelBar(); await sleep(50);
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true })); await sleep(100);
          const e2 = M.findEvent(C.score, ev.id).ev; return [e2.fig || '', e2.notes.length];""")
        check(r == ['', 1], f'the figures of one note removed, the note kept {r}')
        r = await J("""const xml = X.toMusicXML(C.score); const back = X.fromMusicXML(xml); const a1 = M.allStaves(C.score)[0].bars[0].map((e) => M.figRows(e.fig).join(' ')), b1 = M.allStaves(back)[0].bars[0].map((e) => M.figRows(e.fig).join(' '));
          return { a1, b1, n: (xml.match(/<figured-bass>/g) || []).length };""")
        check(r['a1'] == r['b1'] and r['n'] == 3, f'MusicXML keeps the figures {r}')
        r = await J("""const f = async (u) => X.readMusicFile(new File([await (await fetch(u)).arrayBuffer()], u.split('/').pop()));
          const sc = await f('/__corpus/ms/src/importexport/musicxml/tests/data/testFiguredBass1.xml'); const evs = M.allStaves(sc).flatMap((st) => st.bars.flat()).filter((e) => e.fig);
          return evs.map((e) => e.fig);""")
        check(len(r) >= 5 and any('♭' in x for x in r), f'figures from another program {r}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose figured bass')
asyncio.run(main())
