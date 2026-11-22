# Compose guitar tablature: the strings and frets a guitarist would choose (open chords, barre chords,
# a scale in first position, a run held in seventh position, a string asked for, a tied note in
# brackets); the button in Clef shows the tablature under the guitar staff (six lines, TAB, the same
# notes), a tap on a fret number selects its note, nothing is written on the tablature itself; a second
# tap hides it; MusicXML keeps it (a TAB staff with its tuning, strings and frets) and reads tablatures
# from other programs (a staff with its tablature, a bass tablature alone, MuseScore's tests); a
# guitar's strings are ① to ⑥ in Text; no errors.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
CORPUS = '/__corpus/'
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
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const L = await import('/js/compose/engrave.js'); const X = await import('/js/compose/musicxml.js'); const TB = await import('/js/compose/tab.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        # ---- the choice of strings
        r = await J("""const G = [40, 45, 50, 55, 59, 64];
          const sh = (pl) => { const f = Array(6).fill('x'); pl.forEach((c) => { if (c) f[c.i] = c.fret; }); return f.join(''); };
          const ch = { C: [48, 52, 55, 60, 64], G: [43, 47, 50, 55, 59, 67], D: [50, 57, 62, 66], Am: [45, 52, 57, 60, 64], E: [40, 47, 52, 56, 59, 64], F: [41, 48, 53, 57, 60, 65], Bm: [47, 54, 59, 62, 66] };
          const out = {}; for (const [k, v] of Object.entries(ch)) out[k] = sh(TB.placeChord(v, G));
          const run = (start, ms) => { let prev = start; return ms.map((md) => { const [c] = TB.placeChord([md], G, prev); prev = TB.handAfter(prev, [c.fret]); return (6 - c.i) + ':' + c.fret; }).join(' '); };
          out.scale = run(null, [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67]);
          out.high = run(7, [69, 71, 72, 74, 76, 74, 72, 71, 69]);
          out.asked = sh(TB.placeChord([64], G, null, [3]));
          out.bass = sh(TB.placeChord([28], [28, 33, 38, 43])).slice(0, 4);
          return out;""")
        want = {'C': 'x32010', 'G': '320003', 'D': 'xx0232', 'Am': 'x02210', 'E': '022100', 'F': '133211', 'Bm': 'x24432'}
        check(all(r[k] == v for k, v in want.items()), f'open and barre chords as guitarists play them {[(k, r[k]) for k in want]}')
        check(r['scale'] == '5:3 4:0 4:2 4:3 3:0 3:2 2:0 2:1 2:3 1:0 1:1 1:3', f'a C major scale in first position, open strings used {r["scale"]}')
        check(r['high'] == '2:10 1:7 1:8 1:10 1:12 1:10 1:8 1:7 2:10', f'a run high on the neck stays in position {r["high"]}')
        check(r['asked'] == 'xxx9xx' and r['bass'] == '0xxx', f'a string asked for is used; a bass guitar has its own strings {r["asked"]} {r["bass"]}')
        # ---- a guitar piece with its tablature
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Tab', insts: ['guitar'], time: [4, 4], bars: 4 }); await sleep(900);
          const st = M.allStaves(C.score)[0]; const N = (md) => { const pcs = [[0,0],[0,1],[1,0],[1,1],[2,0],[3,0],[3,1],[4,0],[4,1],[5,0],[5,1],[6,0]]; const [s, a] = pcs[md % 12]; return { s: Math.floor(md / 12 - 1) * 7 + s, a }; };
          const ev = (mds, t = 4, extra = {}) => ({ id: M.newId(), t, dots: 0, notes: mds.map(N), ...extra });
          st.bars[0] = [ev([48, 52, 55, 60, 64], 2), ev([43, 47, 50, 55, 59, 67], 2)];
          st.bars[1] = [ev([48]), ev([50]), ev([52]), ev([53])];
          st.bars[2] = [ev([64], 4, { str: 'III' }), ev([64], 4), ev([57], 2)];
          st.bars[2][2].notes[0].tie = true; st.bars[3] = [ev([57], 2), ev([45, 52, 57, 60, 64], 2)];
          C.mode = 'select'; C.sel.clear(); C.sel.add(st.bars[0][0].id); C.tab = 'clef'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(150);""")
        r = await J("return !!document.querySelector('#cpPalBody button[aria-label=\"Tablature\"]')")
        check(r, 'the Tablature button is in Clef for a guitar')
        n0 = await J("return L.layoutScore(C.score).pages[0].systems[0].staves.length")
        await J("document.querySelector('#cpPalBody button[aria-label=\"Tablature\"]').click(); await sleep(250);")
        r = await J("""const lay = L.layoutScore(C.score); const sys = lay.pages[0].systems[0]; const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4); const hit = L.drawPage(g, lay, 0);
          const tabEv = hit.events.filter((e) => e.tab); const byId = {}; for (const e of tabEv) byId[e.id] = e.notes.map((n) => n.str + ':' + n.fret).sort().join(' ');
          const st = M.allStaves(C.score)[0]; const fr = (m, i) => byId[st.bars[m][i].id] || '';
          return { on: !!C.score.parts[0].tab, n: sys.staves.length, lines: sys.staves[1].tab && sys.staves[1].tab.length, below: sys.staves[1].y > sys.staves[0].y + 4,
            C: fr(0, 0), G: fr(0, 1), scale: [0, 1, 2, 3].map((i) => fr(1, i)).join(' '), asked: fr(2, 0), free: fr(2, 1), tied: [...(L.layoutScore(C.score).pages[0].systems[0].staves[1].frets.values())].filter((f) => f.tied).length, Am: fr(3, 1), staffEv: hit.events.filter((e) => !e.tab).length };""")
        check(r['on'] and r['n'] == n0 + 1 and r['lines'] == 6 and r['below'], f'the button shows a six-line tablature under the guitar staff {r}')
        check(r['C'] == '1:0 2:1 3:0 4:2 5:3' and r['G'] == '1:3 2:0 3:0 4:0 5:2 6:3' and r['Am'] == '1:0 2:1 3:2 4:2 5:0', f'the chords in it {r["C"]} | {r["G"]} | {r["Am"]}')
        check(r['scale'] == '5:3 4:0 4:2 4:3', f'the notes one by one {r["scale"]}')
        check(r['asked'] == '3:9' and r['free'] == '1:0' and r['tied'] == 1, f'the string asked for, the same note played freely, a tied note in brackets {r["asked"]} {r["free"]} {r["tied"]}')
        check(r['staffEv'] == 13, f'the staff above still has all its notes {r["staffEv"]}')
        # a tap on a fret number selects its note; the pen does not write on the tablature
        r = await J("""const h = C.hits[0]; const q = h.events.find((e) => e.tab && e.notes.length === 1 && e.m === 1); const p = C.pages[0], rr = p.pg.getBoundingClientRect();
          const x = rr.left + (q.x + 0.6) * p.k, y = rr.top + q.notes[0].y * p.k; C.sel.clear(); T.tapSelect(x, y, false); await sleep(150);
          const picked = [...C.sel][0] === q.id; const ts = h.staves.find((s) => s.tab); const tg = L.hitTest(h, q.x + 0.6, ts.y + 2); return { picked, write: tg };""")
        check(r['picked'] and r['write'] is None, f'a tap on a fret number selects its note; nothing is written on the tablature {r}')
        # MusicXML: a TAB staff with its tuning, strings and frets, read back as the tablature
        r = await J("""const sc = JSON.parse(JSON.stringify(C.score)); sc.parts[0].tuning = [38, 45, 50, 55, 59, 64];
          const xml = X.toMusicXML(sc); const back = X.fromMusicXML(xml); const p0 = back.parts[0];
          const lay = L.layoutScore(back); const fr = [...lay.pages[0].systems[0].staves[1].frets.values()].map((f) => f.str + ':' + f.fret);
          const lay0 = L.layoutScore(sc); const fr0 = [...lay0.pages[0].systems[0].staves[1].frets.values()].map((f) => f.str + ':' + f.fret);
          return { tab: (xml.match(/<sign>TAB<\\/sign>/g) || []).length, tun: (xml.match(/<staff-tuning /g) || []).length, frets: (xml.match(/<fret>/g) || []).length, staves: p0.staves.length, on: !!p0.tab, tuning: (p0.tuning || []).join(), same: fr.join() === fr0.join(), fr: fr.slice(0, 6), fr0: fr0.slice(0, 6) };""")
        check(r['tab'] == 1 and r['tun'] == 6 and r['frets'] >= 20, f'MusicXML writes the tablature: a TAB staff, its six strings, the frets {r}')
        check(r['staves'] == 1 and r['on'] and r['tuning'] == '38,45,50,55,59,64' and r['same'], f'read back: one staff with its tablature, the tuning (drop D) and the same frets {r}')
        # tablatures from other programs
        r = await J("""const f = async (u) => X.readMusicFile(new File([await (await fetch(u)).arrayBuffer()], u.split('/').pop()));
          const out = {};
          for (const [k, u] of [['both', 'osmd/test/data/test_tab_plus_treble_staff_correctNotePositions_pr1703.musicxml'], ['bass', 'osmd/test/data/test_tabs_4_strings_bass_guitar.musicxml'], ['ms1', 'ms/src/importexport/musicxml/tests/data/testTablature1.xml'], ['ms2', 'ms/src/importexport/musicxml/tests/data/testTablature2.xml'], ['ms3', 'ms/src/importexport/musicxml/tests/data/testTablature3.xml'], ['ms5', 'ms/src/importexport/musicxml/tests/data/testTablature5.xml'], ['msall', 'ms/src/importexport/musicxml/tests/data/testTabs_ref.xml'], ['fx', 'osmd/test/data/OSMD_Function_Test_Tablature_Alleffects.musicxml']]) {
            const txt = await (await fetch('""" + CORPUS + """' + u)).text(); const sc = await f('""" + CORPUS + """' + u);
            // the file's own string and fret for each note on its tablature
            const doc = new DOMParser().parseFromString(txt, 'application/xml'); const want = [...doc.querySelectorAll('note')].filter((n) => n.querySelector('technical fret') && !n.querySelector('grace')).map((n) => n.querySelector('technical string').textContent.trim() + ':' + n.querySelector('technical fret').textContent.trim());
            const lay = L.layoutScore(sc); const got = []; for (const pgx of lay.pages) for (const sy of pgx.systems) for (const s of sy.staves) if (s.tab) for (const [n, v] of s.frets) got.push(v.str + ':' + v.fret);
            const parts = sc.parts.map((p) => [p.staves.length, !!p.tab, (p.tuning || M.instOf(p).tuning || []).length]);
            const gotSet = new Map(); for (const g of got) gotSet.set(g, (gotSet.get(g) || 0) + 1); let hit = 0; for (const w of want) if (gotSet.get(w)) { hit++; gotSet.set(w, gotSet.get(w) - 1); }
            out[k] = { parts, want: want.length, hit };
          }
          return out;""")
        both, bass = r['both'], r['bass']
        check(both['parts'][0][:2] == [1, True] and both['hit'] >= both['want'] * 0.9, f'a staff with its tablature: one staff, the tablature under it, the file’s strings and frets {both}')
        check(bass['parts'][0] == [1, True, 4] and bass['hit'] >= bass['want'] * 0.9, f'a bass tablature alone: a staff of notes with the four-string tablature, its strings and frets {bass}')
        for k in ['ms1', 'ms2', 'ms3', 'ms5', 'msall', 'fx']:
            q = r[k]; check(q['parts'] and any(x[1] for x in q['parts']) and q['hit'] >= q['want'] * 0.8, f'{k}: read with its tablature, strings and frets as in the file {q}')
        # off again
        await J("C.tab = 'clef'; T.renderTab(); await sleep(50); document.querySelector('#cpPalBody button[aria-label=\"Tablature\"]').click(); await sleep(200);")
        r = await J("return [!C.score.parts[0].tab, L.layoutScore(C.score).pages[0].systems[0].staves.length]")
        check(r == [True, n0], f'tapped again: the tablature hidden {r}')
        # a guitar's strings in Text: ① to ⑥; a cello's I to IV
        r = await J("""const st = M.allStaves(C.score)[0]; C.sel.clear(); C.sel.add(st.bars[1][0].id); C.tab = 'text'; T.syncSelBar(); T.renderTab(); await sleep(100);
          const g = [...document.querySelectorAll('#cpPalBody button[aria-label^="String "]')].map((b) => b.textContent.trim());
          document.querySelector('#cpPalBody button[aria-label="String 5"]').click(); await sleep(150); const s5 = M.allStaves(C.score)[0].bars[1][0].str;
          await E.createComposition({ title: 'Cello', insts: ['cello'], time: [4, 4], bars: 2 }); await sleep(700); const s2 = M.allStaves(C.score)[0];
          C.sel.clear(); C.sel.add(s2.bars[0][0].id); C.tab = 'text'; T.syncSelBar(); T.renderTab(); await sleep(100);
          const c = [...document.querySelectorAll('#cpPalBody .cp-fing button')].map((b) => b.textContent.trim()).filter((t) => /^I/.test(t));
          const tb = !!document.querySelector('#cpPalBody button[aria-label="Tablature"]'); C.tab = 'clef'; T.renderTab(); await sleep(50);
          return { g, s5, c, tabForCello: !!document.querySelector('#cpPalBody button[aria-label="Tablature"]') };""")
        check(r['g'] == ['①', '②', '③', '④', '⑤', '⑥'] and r['s5'] == 'V', f'a guitar’s strings are ① to ⑥ {r["g"]} {r["s5"]}')
        check(r['c'] == ['I', 'II', 'III', 'IV'] and not r['tabForCello'], f'a cello keeps I to IV and has no tablature {r["c"]} {r["tabForCello"]}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose guitar tablature')
asyncio.run(main())
