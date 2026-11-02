import asyncio, json
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
  await E.createComposition({ title: 'Test', insts: ['cello', 'piano'], time: [3, 8], bars: 8 });
  await new Promise(r => setTimeout(r, 1200));
  const C = window.__compose, T = window.__composeTest;
  const info = M.staffInfo(C.score);
  const cello = info[0];
  const tg = (staff, m, t, p) => ({ staff: { st: staff.st, inst: staff.inst }, meas: { m }, t, p });
  const out = {};
  // 3/8: an eighth then a quarter (written on the second eighth)
  C.tool.dur = 8; C.tool.dots = 0; T.commitWrite(tg(cello, 0, 0, 2));
  C.tool.dur = 4; T.commitWrite(tg(cello, 0, 240, 3));
  out.bar0 = C.score.parts[0].staves[0].bars[0].map(e => (e.rest ? 'r' : '') + e.t + '.'.repeat(e.dots||0) + (e.notes && e.notes[0].tie ? '~' : ''));
  // a lyric and a dynamic on the eighth, then write another pitch over it: they stay
  const ev0 = C.score.parts[0].staves[0].bars[0][0]; ev0.lyric = 'La'; ev0.dyn = 'mf'; ev0.art = ['stacc'];
  C.tool.dur = 8; T.commitWrite(tg(cello, 0, 0, 5));
  const ev0b = C.score.parts[0].staves[0].bars[0][0];
  out.kept = { lyric: ev0b.lyric, dyn: ev0b.dyn, art: ev0b.art, pitch: ev0b.notes[0].s };
  // tuplet starting off the beat in 4/4 (bar 2 gets 4/4)
  M.setTime(C.score, 2, [4, 4]);
  C.tool.dur = 8; C.tool.tup = 3; T.commitWrite(tg(cello, 2, 240, 4)); C.tool.tup = 0;
  out.tupBar = C.score.parts[0].staves[0].bars[2].map(e => (e.rest ? 'r' : '') + e.t + (e.tup ? 't' + e.tup.i : ''));
  const sumTicks = (bar, time) => bar.reduce((a, e) => a + M.ticksOf(e, time), 0);
  out.sums = C.score.parts[0].staves[0].bars.map((b, m) => sumTicks(b, M.timeAt(C.score, m)) === M.barTicks(M.timeAt(C.score, m)));
  // tremolo on a quarter in bar 3, and a whole note with tremolo in bar 4
  C.tool.dur = 4; T.commitWrite(tg(cello, 3, 0, 4)); C.score.parts[0].staves[0].bars[3][0].art = ['trem2'];
  C.tool.dur = 1; T.commitWrite(tg(cello, 4, 0, 4)); C.score.parts[0].staves[0].bars[4][0].art = ['trem'];
  // low cello notes and high piano notes (no collision)
  C.tool.dur = 4; T.commitWrite(tg(cello, 5, 0, -6)); T.commitWrite(tg(info[1], 5, 0, 14));
  // semitone moves on a bar selection, then an octave
  T.selectBars(cello.st, cello.st, 5, 5);
  const before = C.score.parts[0].staves[0].bars[5][0].notes[0];
  T.moveSemis(1); const s1 = C.score.parts[0].staves[0].bars[5][0].notes[0];
  T.moveNotes(7); const s2 = C.score.parts[0].staves[0].bars[5][0].notes[0];
  out.moves = [M.midiOf(before.s, before.a), M.midiOf(s1.s, s1.a), M.midiOf(s2.s, s2.a)];
  // clefs: change to every clef and draw
  for (const c of Object.keys(M.CLEFS)) { C.score.parts[0].staves[0].clef = c; window.__composeRelayout(); }
  C.score.parts[0].staves[0].clef = 'bass';
  // a slur over bar 3-4
  C.score.spans = C.score.spans || []; C.score.spans.push({ id: 'sl1', kind: 'slur', st: cello.st.id, v: 1, a: { m: 3, pos: 0 }, b: { m: 4, pos: 0 } });
  window.__composeRelayout();
  await new Promise(r => setTimeout(r, 600));
  out.spanHits = (C.hits || []).reduce((a, h) => a + ((h && h.spans) || []).length, 0);
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' and 'TUNNEL' not in m.text and 'peerjs' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(JS)
        print(json.dumps(r, indent=1))
        await pg.screenshot(path='/home/claude/shots/comp.png')
        print(errs); await b.close()
asyncio.run(main())
