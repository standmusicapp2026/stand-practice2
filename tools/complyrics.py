# Compose lyrics with several verses: typing verse 1 and verse 2 under the same notes, each on its own
# line; a verse's syllable removed alone; room under the staff for every verse; the words never run
# into each other; MusicXML keeps every verse (export and import again), files numbered 2 and 3 (or by
# names) come in as verses 1 and 2; no errors.
import asyncio, os, sys
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
        J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const X = await import('/js/compose/musicxml.js'); const C = window.__compose, T = window.__composeTest; " + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Verses', insts: ['voice'], time: [4, 4], bars: 4 }); await sleep(900);
          const info = M.staffInfo(C.score); const tg = (x, m, t, p) => ({ staff: { st: x.st, inst: x.inst }, meas: { m }, t, p });
          C.tool.dur = 4; C.tool.dots = 0; for (let m = 0; m < 2; m++) for (let i = 0; i < 4; i++) T.commitWrite(tg(info[0], m, i * 480, i % 3));
          C.undo = []; C.mode = 'select'; await sleep(200);""")
        # type verse 1 then verse 2 through the palette
        async def typeVerse(v, words):
            await J(f"""const st = M.allStaves(C.score)[0]; C.markSel = null; C.selBars = null; C.sel.clear(); C.sel.add(st.bars[0][0].id);
              C.tab = 'text'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(100);
              const vb = document.querySelector('#cpPalBody button[aria-label="Verse {v}"]'); vb.click(); await sleep(100);""")
            for w in words:
                inp = pg.locator('#cpPalBody input[aria-label="Lyrics"]')
                await inp.fill(w.rstrip('-'))
                await inp.press('-' if w.endswith('-') else 'Enter')
                await pg.wait_for_timeout(60)
        await typeVerse(1, ['Twin-', 'kle', 'twin-', 'kle', 'lit-', 'tle', 'star'])
        await typeVerse(2, ['Up', 'a-', 'bove', 'the', 'world', 'so', 'high'])
        r = await J("""const st = M.allStaves(C.score)[0]; const evs = [...st.bars[0], ...st.bars[1]];
          return { v1: evs.map((e) => M.lyricOf(e, 1)), v2: evs.map((e) => M.lyricOf(e, 2)), pressed: document.querySelector('#cpPalBody button[aria-label="Verse 2"]').getAttribute('aria-pressed') };""")
        check(r['v1'][:7] == ['Twin-', 'kle', 'twin-', 'kle', 'lit-', 'tle', 'star'], f"verse 1 typed under the notes {r['v1']}")
        check(r['v2'][:7] == ['Up', 'a-', 'bove', 'the', 'world', 'so', 'high'], f"verse 2 typed under the same notes, verse 1 kept {r['v2']}")
        check(r['pressed'] == 'true', 'the verse button shows which verse is typed')
        # drawn: two lines, verse 2 lower; room below the staff for both
        r = await J("""const L = await import('/js/compose/engrave.js'); const lay = L.layoutScore(C.score); const c = document.createElement('canvas'); c.width = lay.W * 4; c.height = lay.H * 4; const g = c.getContext('2d'); g.scale(4, 4);
          const hit = L.drawPage(g, lay, 0); const marks = (hit.marks || []).filter((m) => m.kind === 'lyric');
          const y1 = marks.filter((m) => m.verse === 1).map((m) => m.y0), y2 = marks.filter((m) => m.verse === 2).map((m) => m.y0);
          // words of one line never overlap
          let overlap = 0; for (const v of [1, 2]) { const ms = marks.filter((m) => m.verse === v).sort((a, b) => a.x0 - b.x0); for (let i = 1; i < ms.length; i++) if (Math.abs(ms[i].y0 - ms[i - 1].y0) < 0.1 && ms[i].x0 < ms[i - 1].x1 - 0.2) overlap++; }
          const one = JSON.parse(JSON.stringify(C.score)); for (const st of M.allStaves(one)) for (const bar of st.bars) for (const e of bar) delete e.lyricV;
          const lay1 = L.layoutScore(one);
          return { n1: y1.length, n2: y2.length, dy: y2.length && y1.length ? +(y2[0] - y1[0]).toFixed(2) : 0, overlap, h2: lay.pages[0].systems[0].height + (lay.pages[0].systems[1] ? lay.pages[0].systems[1].top - lay.pages[0].systems[0].top : 0), sys: lay.pages[0].systems.map((s) => +s.top.toFixed(1)), sys1: lay1.pages[0].systems.map((s) => +s.top.toFixed(1)) };""")
        check(r['n1'] >= 7 and r['n2'] >= 7 and r['dy'] > 2, f"two lines of words, verse 2 under verse 1 {r}")
        check(r['overlap'] == 0, f"no syllable runs into the next {r['overlap']}")
        check(len(r['sys']) < 2 or len(r['sys1']) < 2 or (r['sys'][1] - r['sys'][0]) >= (r['sys1'][1] - r['sys1'][0]), f"a second verse takes room under the staff {r['sys']} {r['sys1']}")
        # removing one verse's syllable leaves the other
        r = await J("""const st = M.allStaves(C.score)[0]; const ev = st.bars[0][1];
          C.sel.clear(); C.markSel = { id: ev.id, kind: 'lyric', name: M.lyricOf(ev, 2), verse: 2, m: 0 }; T.syncSelBar(); await sleep(50);
          const del = [...document.querySelectorAll('button')].find((b) => b.offsetParent && /^(Delete|Remove)$/.test((b.getAttribute('aria-label') || b.textContent || '').trim()));
          if (del) del.click(); else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true })); await sleep(100);
          const e2 = M.findEvent(C.score, ev.id).ev; return { v1: M.lyricOf(e2, 1), v2: M.lyricOf(e2, 2) };""")
        check(r['v1'] == 'kle' and r['v2'] == '', f"verse 2's syllable removed, verse 1 kept {r}")
        # MusicXML: out and in again
        r = await J("""const xml = X.toMusicXML(C.score); const back = X.fromMusicXML(xml); const a = M.allStaves(C.score)[0], b = M.allStaves(back)[0];
          const same = [0, 1].every((m) => a.bars[m].every((e, i) => M.lyricOf(e, 1) === M.lyricOf(b.bars[m][i], 1) && M.lyricOf(e, 2) === M.lyricOf(b.bars[m][i], 2)));
          return { same, n2: (xml.match(/<lyric number="2">/g) || []).length };""")
        check(r['same'] and r['n2'] == 6, f"MusicXML keeps both verses {r}")
        r = await J("""const f = async (u) => X.readMusicFile(new File([await (await fetch(u)).arrayBuffer()], u.split('/').pop()));
          const cnt = (sc) => { const vs = {}; for (const st of M.allStaves(sc)) for (const bar of st.bars) for (const e of bar) for (let v = 1; v <= M.versesOf(e); v++) if (M.lyricOf(e, v)) vs[v] = (vs[v] || 0) + 1; return vs; };
          const a = await f('/__corpus/osmd/test/data/Cornelius_P_Christbaum_Opus_8_1_1865.mxl'), b = await f('/__corpus/m21/music21/corpus/bach/bwv297.mxl'), c = await f('/__corpus/ms/src/importexport/musicxml/tests/data/testNumberedLyrics.xml');
          return { a: cnt(a), b: cnt(b), c: cnt(c) };""")
        check(r['a'].get('1', 0) > 100 and r['a'].get('2', 0) >= 2, f"a song with a second verse: both come in {r['a']}")
        check(r['b'].get('1', 0) > 30 and '2' not in r['b'], f"words numbered 2 in the file are the first line {r['b']}")
        check(set(r['c'].keys()) == {'1', '2'}, f"verses numbered 3 and 4, or named, are lines 1 and 2 of their part {r['c']}")
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('PASS' if not fails else 'FAIL', 'compose lyrics with several verses')
asyncio.run(main())
