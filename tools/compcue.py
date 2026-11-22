# Compose cue notes and small notes, and drums on one line: the Size buttons make the selected notes
# cue notes (small, not played) or small notes (played); drawn smaller; MusicXML keeps them (<cue/>,
# size="cue") and reads them from other programs; a snare drum or cymbals on a one-line staff
# (stems up, cymbals with x heads, whole rests hanging from the line, short barlines), kept through
# MusicXML; other instruments keep five lines; no errors.
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
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const X = await import('/js/compose/musicxml.js'); const L = await import('/js/compose/engrave.js'); const P = await import('/js/compose/playback.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Cues', insts: ['violin', 'snare', 'cymbals', 'tomtoms'], time: [4, 4], bars: 4 }); await sleep(900);
          const info = M.staffInfo(C.score); const tg = (x, m, t, p) => ({ staff: { st: x.st, inst: x.inst }, meas: { m }, t, p });
          C.tool.dur = 4; C.tool.dots = 0; for (let m = 0; m < 2; m++) for (let i = 0; i < 4; i++) { T.commitWrite(tg(info[0], m, i * 480, i)); T.commitWrite(tg(info[1], m, i * 480, 4)); T.commitWrite(tg(info[2], m, i * 480, 4)); }
          C.undo = []; C.mode = 'select'; await sleep(200);""")
        click = lambda label: J(f"""const st = M.allStaves(C.score)[0]; C.markSel = null; C.selBars = null; C.sel.clear(); a.forEach((i) => C.sel.add(st.bars[0][i].id));
          C.tab = 'notes'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(80);
          const bt = [...document.querySelectorAll('#cpPalBody button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('{label}')); bt.click(); await sleep(120);
          return st.bars[0].map((e) => (e.cue ? 'c' : e.small ? 's' : '-')).join('');""", None)
        r = await J("""const st = M.allStaves(C.score)[0]; C.sel.clear(); [0, 1].forEach((i) => C.sel.add(st.bars[0][i].id)); C.tab = 'notes'; T.renderTab(); await sleep(80);
          const bt = [...document.querySelectorAll('#cpPalBody button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Cue notes')); bt.click(); await sleep(120);
          C.sel.clear(); C.sel.add(st.bars[0][2].id); T.renderTab(); await sleep(80);
          const b2 = [...document.querySelectorAll('#cpPalBody button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Small notes')); b2.click(); await sleep(120);
          return st.bars[0].map((e) => (e.cue ? 'c' : e.small ? 's' : '-')).join('');""")
        check(r == 'ccs-', f'Size buttons: two cue notes, one small note {r}')
        r = await J("""const st = M.allStaves(C.score)[0]; C.sel.clear(); C.sel.add(st.bars[0][0].id); T.renderTab(); await sleep(80);
          const bt = [...document.querySelectorAll('#cpPalBody button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Cue notes')); const was = bt.classList.contains('on'); bt.click(); await sleep(120);
          const s1 = st.bars[0].map((e) => (e.cue ? 'c' : e.small ? 's' : '-')).join(''); T.renderTab(); await sleep(50);
          const bt2 = [...document.querySelectorAll('#cpPalBody button')].find((x) => (x.getAttribute('aria-label') || '').startsWith('Cue notes')); bt2.click(); await sleep(120);
          return { was, s1, s2: st.bars[0].map((e) => (e.cue ? 'c' : e.small ? 's' : '-')).join('') };""")
        check(r['was'] and r['s1'] == '-cs-' and r['s2'] == 'ccs-', f'the button shows it is on, and a second tap gives normal size again {r}')
        # played: cue notes not, small notes yes
        r = await J("""const tl = P.buildTimeline(C.score, { from: 0 }); const st = M.allStaves(C.score)[0]; const ids = new Set(tl.notes.flatMap((n) => n.ids || (n.id ? [n.id] : [])));
          return { cue: [0, 1].map((i) => ids.has(st.bars[0][i].id)), small: ids.has(st.bars[0][2].id), normal: ids.has(st.bars[0][3].id), any: ids.size };""")
        check(r['any'] > 0 and r['cue'] == [False, False] and r['small'] and r['normal'], f'cue notes are not played; small notes are {r}')
        # drawn smaller: the stem of a cue note is shorter
        r = await J("""const lay = L.layoutScore(C.score); const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4); const hit = L.drawPage(g, lay, 0);
          const v = hit.events.filter((e) => e.staff === 0 && e.m === 0 && !e.rest); const len = (e) => Math.abs(e.stemTip - e.notes[0].y);
          return { lens: v.map((e) => +len(e).toFixed(2)), lines: [0, 1, 2, 3].map((k) => L.linesOf(lay.pages[0].systems[0].staves[k])) };""")
        check(r['lens'][0] < r['lens'][3] * 0.8 and r['lens'][2] < r['lens'][3] * 0.8, f'cue and small notes drawn smaller (stem lengths) {r["lens"]}')
        check(r['lines'] == [5, 1, 1, 5], f'snare drum and cymbals on one line; violin and tom-toms on five {r["lines"]}')
        r = await J("""const lay = L.layoutScore(C.score); const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4); const hit = L.drawPage(g, lay, 0);
          const sn = hit.events.filter((e) => e.staff === 1 && !e.rest), cy = hit.events.filter((e) => e.staff === 2 && !e.rest);
          return { up: sn.every((e) => e.up) && cy.every((e) => e.up), y: [...new Set(sn.map((e) => +(e.notes[0].y - e.y).toFixed(2)))] };""")
        check(r['up'] and r['y'] == [2], f'drum notes on the line, stems up {r}')
        # MusicXML
        r = await J("""const xml = X.toMusicXML(C.score); const back = X.fromMusicXML(xml); const s0 = M.allStaves(back)[0];
          return { cue: (xml.match(/<cue\\/>/g) || []).length, size: (xml.match(/size="cue"/g) || []).length, lines: (xml.match(/<staff-lines>1<\\/staff-lines>/g) || []).length,
            back: s0.bars[0].map((e) => (e.cue ? 'c' : e.small ? 's' : '-')).join(''), blines: M.allStaves(back).map((st) => st.lines || M.instOf(back.parts.find((p) => p.staves.includes(st))).lines || 5) };""")
        check(r['cue'] == 2 and r['size'] == 3 and r['back'] == 'ccs-', f'MusicXML keeps cue and small notes {r}')
        check(r['lines'] == 2 and r['blines'] == [5, 1, 1, 5], f'MusicXML keeps the one-line staves {r}')
        r = await J("""const f = async (u) => X.readMusicFile(new File([await (await fetch(u)).arrayBuffer()], u.split('/').pop()));
          const sc = await f('/__corpus/ms/src/importexport/musicxml/tests/data/testCueNotes.xml'); const evs = M.allStaves(sc).flatMap((st) => st.bars.flat());
          return { cue: evs.filter((e) => e.cue).length, small: evs.filter((e) => e.small).length };""")
        check(r['cue'] >= 2, f'cue notes from another program {r}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose cue notes, small notes, one-line percussion')
asyncio.run(main())
