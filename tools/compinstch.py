# Compose: a part that changes instrument (flute to piccolo, clarinet in B♭ to clarinet in A) from a
# bar on: chosen in Bars; the name over the staff; the written notes and the key follow the new
# instrument's transposition (a new key signature where it changes); played with its sound; the line
# name at the next line is the new instrument; MusicXML keeps the sounding notes; "no change" undoes
# it; parts without a change are as before; no errors.
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
        await J("""await E.createComposition({ title: 'Doubling', insts: ['flute', 'clarinet'], time: [4, 4], bars: 12, key: 0 }); await sleep(900);
          const info = M.staffInfo(C.score);
          // the same sounding notes in every bar: C5 D5 E5 F5 (flute) and C4 D4 E4 F4 (clarinet), written straight into the model
          for (const [k, base] of [[0, 35], [1, 28]]) for (let m = 0; m < 12; m++) { const st = info[k].st; st.bars[m] = [0, 1, 2, 3].map((i) => ({ id: M.newId(), t: 4, dots: 0, notes: [{ s: base + i, a: 0 }] })); }
          C.layout = null; window.__composeRelayout(); C.undo = []; C.mode = 'select'; await sleep(200);""")
        # choose in Bars: bar 5 of the flute → piccolo; bar 5 of the clarinet → clarinet in A
        async def choose(staff, m, val):
            return await J(f"""const st = M.allStaves(C.score)[{staff}]; T.selectBars(st, st, {m}, {m}); C.tab = 'bars'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(80);
              const sel = document.querySelector('#cpPalBody select[aria-label="Instrument from this bar"]'); if (!sel) return 'no select';
              sel.value = '{val}'; sel.dispatchEvent(new Event('change')); await sleep(150); return JSON.stringify(C.score.parts[{staff}].instCh || null);""")
        r1 = await choose(0, 4, 'piccolo'); r2 = await choose(1, 4, 'clarinetA')
        check(r1 == '{"4":"piccolo"}' and r2 == '{"4":"clarinetA"}', f'chosen in Bars, from bar 5 {r1} {r2}')
        r = await J("""const lay = L.layoutScore(C.score, { concert: false }); const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4);
          const out = { ys: {}, names: [] }; for (let pi = 0; pi < lay.pages.length; pi++) { const hit = L.drawPage(g, lay, pi); for (const e of hit.events) { if (e.rest) continue; const k = e.staff + ':' + e.m; if (!(k in out.ys)) out.ys[k] = +(e.notes[0].y - e.y).toFixed(2); } }
          const sc = (st, m) => M.allStaves(C.score)[st].bars[m][0].notes[0];
          out.w = [0, 1].map((st) => [3, 4].map((m) => M.toWritten(sc(st, m), M.instAt(C.score.parts[st], m)).s));
          return out;""")
        w = r['w']
        check(w[0][0] - w[0][1] == 7, f'flute to piccolo: written an octave lower from the change (the piccolo sounds an octave up) {w[0]}')
        check(w[1][1] - w[1][0] == 1, f'clarinet in B♭ to A: written a step higher from the change {w[1]}')
        check(abs((r['ys']['0:3'] - r['ys']['0:4']) - (-3.5)) < 0.01 or abs((r['ys']['0:4'] - r['ys']['0:3']) - 3.5) < 0.01, f'drawn where written {r["ys"].get("0:3")} {r["ys"].get("0:4")}')
        # key: concert C → B♭ clarinet D major (2 sharps), A clarinet E♭ major (3 flats)
        r = await J("""const p = C.score.parts[1]; return [M.writtenKey(0, M.instAt(p, 3)), M.writtenKey(0, M.instAt(p, 4))];""")
        check(r == [2, -3], f'the written key follows: D major then E♭ major {r}')
        r = await J("""const tl = P.buildTimeline(C.score, { from: 0 }); const by = {}; for (const n of tl.notes) { const k = n.part + ':' + n.sid; by[k] = (by[k] || 0) + 1; }
          const f = tl.notes.filter((n) => n.part === C.score.parts[0].id); return { sids: [...new Set(f.map((n) => n.sid))], midis: [...new Set(f.map((n) => n.midi))].sort((a, b) => a - b), n: f.length };""")
        check('flute' in r['sids'] and 'piccolo' in r['sids'] and r['midis'] == [72, 74, 76, 77] and r['n'] == 48, f'played: flute, then the piccolo sound, the same notes {r}')
        r = await J("""const xml = X.toMusicXML(C.score); const back = X.fromMusicXML(xml); const same = [0, 1].every((pi) => back.parts[pi].staves[0].bars.every((bar, m) => bar.every((e, i) => e.notes[0].s === C.score.parts[pi].staves[0].bars[m][i].notes[0].s && (e.notes[0].a || 0) === (C.score.parts[pi].staves[0].bars[m][i].notes[0].a || 0))));
          return { same, words: (xml.match(/Piccolo<\\/words>|Clarinet in A<\\/words>/g) || []).length, tr: (xml.match(/<transpose>/g) || []).length };""")
        check(r['same'] and r['words'] == 2 and r['tr'] >= 3, f'MusicXML: the same sounding notes, the change named, the transposition stated {r}')
        r = await choose(0, 4, '')
        check(r == 'null', f'"No change here" takes it away {r}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose change of instrument')
asyncio.run(main())
