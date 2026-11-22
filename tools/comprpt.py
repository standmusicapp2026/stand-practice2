# Compose: the bar-repeat sign (％). Chosen in Bars for the selected bars; drawn in the middle of the
# bar; played as the bar before; written out in MusicXML; never merged into a long rest in a part;
# writing a note in such a bar makes it an ordinary bar; tapped again, the bars are empty again.
import asyncio, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
SHOT = os.environ.get('SHOT', '')
fails = []
def check(c, m):
    print(('ok   ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
PRE = "const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const L = await import('/js/compose/engrave.js'); const P = await import('/js/compose/playback.js'); const X = await import('/js/compose/musicxml.js'); const C = window.__compose, T = window.__composeTest; "
async def main():
    async with async_playwright() as p:
        b = await getattr(p, BR).launch()
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True, device_scale_factor=2)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (a) => { " + PRE + js + " }", a)
        await J("document.querySelector('#welGo')?.click(); await sleep(400); document.querySelectorAll('.tour').forEach(x => x.remove());")
        await J("""await E.createComposition({ title: 'Repeat', insts: ['cello', 'violin'], time: [4, 4], bars: 12, key: 0 }); await sleep(900);
          const st = C.score.parts[0].staves[0]; st.bars[0] = [0, 1, 2, 3].map((i) => ({ id: M.newId(), t: 4, dots: 0, notes: [{ s: 21 + i, a: 0 }] }));
          window.__composeRelayout(); C.undo = []; C.mode = 'select';""")
        # Bars: select bars 2–3 of the cello, then "Bar repeat"
        r = await J("""const st = C.score.parts[0].staves[0]; T.selectBars(st, st, 1, 2); C.tab = 'bars'; window.__composeRelayout(); T.syncSelBar(); T.renderTab(); await sleep(100);
          const btn = [...document.querySelectorAll('#cpPalBody button')].find((b) => /Bar repeat/.test(b.textContent)); if (!btn) return 'no button'; btn.click(); await sleep(300);
          return [1, 2].map((m) => M.isBarRepeat(st.bars[m]));""")
        check(r == [True, True], f'Bars → Bar repeat: the selected bars repeat the bar before {r}')
        if SHOT: await pg.screenshot(path=f'{SHOT}/cp_rpt.png')
        # drawn: the sign, not a rest, in the middle of the bar
        r = await J("""const lay = C.lay; const c = document.createElement('canvas'); c.width = lay.W * 3; c.height = lay.H * 3; const g = c.getContext('2d'); g.scale(3, 3);
          const calls = []; const ft = g.fillText.bind(g); g.fillText = (t, x, y) => { calls.push(t); return ft(t, x, y); }; L.drawPage(g, lay, 0);
          return calls.filter((t) => t === '\\uE500').length;""")
        check(r == 2, f'drawn: two bar-repeat signs ({r})')
        # played: bars 2 and 3 sound as bar 1
        r = await J("""const tl = P.buildTimeline(C.score, { from: 0, humanize: false }); const pid = C.score.parts[0].id; const f = tl.notes.filter((n) => n.part === pid).sort((a, b) => a.t - b.t);
          return { n: f.length, m: f.map((n) => n.midi) };""")
        check(r['n'] == 12 and r['m'][:4] == r['m'][4:8] == r['m'][8:12], f'played: the bar three times {r}')
        r = await J("""const xml = X.toMusicXML(C.score); const back = X.fromMusicXML(xml); const st = back.parts[0].staves[0]; return [0, 1, 2, 3].map((m) => st.bars[m].filter((e) => e.notes).length);""")
        check(r == [4, 4, 4, 0], f'MusicXML: written out as notes {r}')
        r = await J("""const lay = L.layoutScore(C.score, { partIndex: 0, multiRests: true }); const ms = []; for (const pg2 of lay.pages) for (const sy of pg2.systems) for (const q of sy.measures) ms.push([q.m, q.end]); return ms.slice(0, 4);""")
        check(r[1] == [1, 1] and r[2] == [2, 2], f'a part: never merged into a long rest {r}')
        # the source bar changed: the repeats follow
        r = await J("""const st = C.score.parts[0].staves[0]; st.bars[0][0].notes = [{ s: 28, a: 0 }]; const tl = P.buildTimeline(C.score, { from: 0, humanize: false }); const pid = C.score.parts[0].id;
          return tl.notes.filter((n) => n.part === pid).sort((a, b) => a.t - b.t).filter((_, i) => i % 4 === 0).map((n) => n.midi);""")
        check(len(set(r)) == 1, f'the bar before changed: the repeats play it as it is now {r}')
        # tapped again: empty bars
        r = await J("""const st = C.score.parts[0].staves[0]; T.selectBars(st, st, 1, 2); T.renderTab(); await sleep(80);
          [...document.querySelectorAll('#cpPalBody button')].find((b) => /Bar repeat/.test(b.textContent)).click(); await sleep(300);
          return [1, 2].map((m) => [M.isBarRepeat(st.bars[m]), st.bars[m].every((e) => e.rest)]);""")
        check(r == [[False, True], [False, True]], f'Bar repeat again: empty bars {r}')
        # the first bar can't repeat anything; undo brings the signs back
        r = await J("""const st = C.score.parts[0].staves[0]; T.selectBars(st, st, 0, 0); T.renderTab(); await sleep(80);
          [...document.querySelectorAll('#cpPalBody button')].find((b) => /Bar repeat/.test(b.textContent)).click(); await sleep(200);
          const a = M.isBarRepeat(st.bars[0]); document.querySelector('#cpPalUndo').click(); await sleep(200);
          const st2 = C.score.parts[0].staves[0]; return [a, M.isBarRepeat(st2.bars[1]), M.isBarRepeat(st2.bars[2])];""")
        check(r == [False, True, True], f'not the first bar; undo brings the signs back {r}')
        # a note written into a ％ bar: an ordinary bar, no sign left anywhere in it
        r = await J("""const st = C.score.parts[0].staves[0], info = M.staffInfo(C.score)[0]; C.tool.dur = 4; C.tool.rest = false; C.tool.acc = null;
          T.commitWrite({ staff: { st: info.st, inst: info.inst }, meas: { m: 1 }, t: 0, p: 3 }); await sleep(100);
          const st2 = C.score.parts[0].staves[0]; return [M.isBarRepeat(st2.bars[1]), st2.bars[1].some((e) => e.rpt && e.full), st2.bars[1].filter((e) => e.notes).length];""")
        check(r[0] is False and r[1] is False and r[2] == 1, f'writing into it makes it an ordinary bar {r}')
        check(not errs, f'no errors {errs[:3]}')
        await b.close()
    print('FAILS', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
