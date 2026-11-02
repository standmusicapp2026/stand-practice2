# Compose: pickup bar, copy/paste of bars with voice 2 and lines, cut, respell
import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const P = await import('/js/compose/playback.js'); const X = await import('/js/compose/musicxml.js'); const G = await import('/js/compose/engrave.js');
  await E.createComposition({ title: 'New things', insts: ['violin'], time: [4, 4], bars: 8 });
  await sleep(800);
  const C = window.__compose, T = window.__composeTest, S = C.score, st = S.parts[0].staves[0];
  const info = M.staffInfo(S)[0];
  const tg = (m, t, p) => ({ staff: { st: info.st, inst: info.inst }, meas: { m }, t, p });
  const out = {};
  // pickup of one beat, one quarter in it, then full bars
  M.setPickup(S, 480);
  C.tool.dur = 4; C.tool.dots = 0;
  T.commitWrite(tg(0, 0, 4));
  for (let m = 1; m < 3; m++) for (let b = 0; b < 4; b++) T.commitWrite(tg(m, b * 480, (m + b) % 7));
  out.pickupBar = st.bars[0].map((e) => (e.rest ? 'r' : 'n') + e.t);
  out.bar1 = st.bars[1].map((e) => (e.rest ? 'r' : 'n') + e.t);
  const tl = P.buildTimeline(S, {}); const n1 = tl.notes.find((n) => n.m === 1); const n0 = tl.notes.find((n) => n.m === 0);
  out.timing = { pickupAt: +n0.t.toFixed(2), bar1At: +n1.t.toFixed(2), beat: +(60 / 96).toFixed(2) };
  const lay = G.layoutScore(S); out.numbers = lay.pages[0].systems.map((s) => M.barNumber(S, s.measures[0].m));
  const xml = X.toMusicXML(S); out.xml = { implicit: /measure number="0" implicit="yes"/.test(xml), bar1: /measure number="1">/.test(xml) };
  const back = X.fromMusicXML ? X.fromMusicXML(xml) : (X.importMusicXML ? await X.importMusicXML(xml) : null);
  if (back) { const sc2 = back.score || back; out.reimport = { pickup: M.pickupOf(sc2), bar0: sc2.parts[0].staves[0].bars[0].map((e) => (e.rest ? 'r' : 'n') + e.t) }; }
  // time change at the start keeps the pickup
  M.setTime(S, 0, [3, 4]); out.after34 = { pickup: M.pickupOf(S), bar0: st.bars[0].map((e) => (e.rest ? 'r' : 'n') + e.t), bar1len: st.bars[1].reduce((a, e) => a + M.ticksOf(e, M.timeAt(S, 1)), 0) };
  M.setTime(S, 0, [4, 4]);
  // voice 2 and a slur in bar 2, copied with the bar to bar 5
  const v2 = M.voiceView(st, 2, S); v2.bars[2] = [{ id: M.newId(), t: 2, dots: 0, notes: [{ s: 28, a: 0 }] }, { id: M.newId(), t: 2, dots: 0, notes: [{ s: 27, a: 0 }] }];
  S.spans = [{ id: 'sl', kind: 'slur', st: st.id, v: 1, a: { m: 2, pos: 0 }, b: { m: 2, pos: 1440 } }];
  T.selectBars(st, st, 2, 2); T.copySel();
  T.selectBars(st, st, 5, 5); T.pasteClip(C.clip);
  out.paste = { notes2: st.bars[2].filter((e) => !e.rest).length, notes5: st.bars[5].filter((e) => !e.rest).length, v2in5: (st.v2 && st.v2[5] || []).filter((e) => !e.rest).length, slur5: S.spans.some((q) => q.kind === 'slur' && q.a.m === 5 && q.b.m === 5) };
  // cut empties
  T.selectBars(st, st, 5, 5); T.cutSel(); out.cut = st.bars[5].every((e) => e.rest);
  // respell F# -> Gb
  st.bars[6] = [{ id: 'rs', t: 1, dots: 0, notes: [{ s: 31, a: 1 }] }]; C.sel.clear(); C.selBars = null; C.sel.add('rs'); T.respell(); const n = st.bars[6][0].notes[0];
  out.respell = M.noteName(n.s, n.a); T.respell(); out.respell2 = M.noteName(st.bars[6][0].notes[0].s, st.bars[6][0].notes[0].a);
  T.toggleCautionary(); out.cau = !!st.bars[6][0].notes[0].cau;
  // bars added before the pickup turn it into a whole bar
  M.addBars(S, 1, 0); out.addBefore = { pickup: M.pickupOf(S), bar1: S.parts[0].staves[0].bars[1].reduce((a, e) => a + M.ticksOf(e, M.timeAt(S, 1)), 0) };
  return out;
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        print(json.dumps(await pg.evaluate(JS), ensure_ascii=False)); print(errs[:4]); await b.close()
asyncio.run(main())
