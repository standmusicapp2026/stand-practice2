# Composer: every element can be tapped on its own and deleted; Empty clears everything
import asyncio, json
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
  await E.createComposition({ title: 'Edit test', insts: ['cello'], time: [4, 4], bars: 12 });
  await new Promise(r => setTimeout(r, 1000));
  const C = window.__compose, T = window.__composeTest, S = C.score, st = S.parts[0].staves[0];
  const info = M.staffInfo(S)[0];
  const tg = (m, t, p) => ({ staff: { st: info.st, inst: info.inst }, meas: { m }, t, p });
  C.tool.dur = 4; C.tool.dots = 0;
  for (let m = 0; m < 8; m++) for (let b = 0; b < 4; b++) T.commitWrite(tg(m, b * 480, (m + b) % 7));
  // everything a score can hold
  S.measures[2].key = 2; M.setTime(S, 4, [3, 4]); st.clefs = { 3: 'tenor' };
  S.measures[1].tempo = { bpm: 72, beat: 4, text: 'Adagio' }; S.measures[5].rehearsal = 'A'; S.measures[6].bar = 'repeat'; S.measures[5].start = 'repeat'; S.measures[7].mark = 'segno';
  const ev = (m, i) => st.bars[m][i];
  ev(0, 0).dyn = 'p'; ev(0, 1).art = ['stacc']; ev(0, 2).chord = 'Am7'; ev(1, 0).lyric = 'la'; ev(1, 1).notes.forEach((n) => { n.tie = true; }); ev(1, 2).notes = ev(1, 1).notes.map((n) => ({ ...n, tie: false })); ev(2, 0).txt = 'dolce'; ev(2, 1).fing = '3';
  ev(3, 2).clef = 'treble';
  S.spans = [
    { id: 'sl', kind: 'slur', st: st.id, v: 1, a: { m: 0, pos: 0 }, b: { m: 0, pos: 1440 } },
    { id: 'hp', kind: 'hairpin', st: st.id, v: 1, dir: '<', a: { m: 1, pos: 0 }, b: { m: 1, pos: 1440 } },
    { id: 'ot', kind: '8va', st: st.id, a: { m: 5, pos: 0 }, b: { m: 5, pos: 960 } },
    { id: 'pd', kind: 'ped', st: st.id, a: { m: 6, pos: 0 }, b: { m: 6, pos: 960 } },
    { id: 'tr', kind: 'trill', st: st.id, a: { m: 7, pos: 0 }, b: { m: 7, pos: 960 } },
    { id: 'vo', kind: 'volta', st: st.id, n: 1, a: { m: 6, pos: 0 }, b: { m: 6, pos: 0 } },
    { id: 'ri', kind: 'rit', st: st.id, a: { m: 2, pos: 0 }, b: { m: 3, pos: 0 } },
  ];
  window.__composeRelayout(); await new Promise(r => setTimeout(r, 500));
  // the client point of a hit box
  const at = (box, i) => { const p = C.pages[i], r = p.pg.getBoundingClientRect(); return [r.left + (box.x0 + box.x1) / 2 * p.k, r.top + (box.y0 + box.y1) / 2 * p.k]; };
  const find = (pred, spans) => { for (let i = 0; i < C.hits.length; i++) { const h = C.hits[i]; if (!h) continue; const l = (spans ? h.spans : h.marks) || []; const b = l.find(pred); if (b) return [b, i]; } return null; };
  const want = [
    ['clef change', (b) => b.kind === 'clef' && b.m === 3, false], ['mid-bar clef', (b) => b.kind === 'evclef', false],
    ['key', (b) => b.kind === 'key' && b.m === 2, false], ['time', (b) => b.kind === 'time' && b.m === 4, false],
    ['tempo', (b) => b.kind === 'tempo', false], ['rehearsal', (b) => b.kind === 'rehearsal', false], ['end repeat', (b) => b.kind === 'barline', false], ['start repeat', (b) => b.kind === 'repstart', false], ['segno', (b) => b.kind === 'mmark', false],
    ['dynamic', (b) => b.kind === 'dyn', false], ['staccato', (b) => b.kind === 'art', false], ['chord', (b) => b.kind === 'chord', false], ['lyric', (b) => b.kind === 'lyric', false], ['tie', (b) => b.kind === 'tie', false], ['words', (b) => b.kind === 'txt', false], ['fingering', (b) => b.kind === 'fing', false],
    ['slur', (b) => b.id === 'sl', true], ['hairpin', (b) => b.id === 'hp', true], ['8va', (b) => b.id === 'ot', true], ['pedal', (b) => b.id === 'pd', true], ['trill line', (b) => b.id === 'tr', true], ['ending', (b) => b.id === 'vo', true], ['rit.', (b) => b.id === 'ri', true],
    ['first clef', (b) => b.kind === 'clef' && b.m === 0, false], ['first time', (b) => b.kind === 'time' && b.m === 0, false],
  ];
  const out = {};
  for (const [name, pred, spans] of want) {
    window.__composeRelayout(); await new Promise(r => setTimeout(r, 120));
    const f = find(pred, spans); if (!f) { out[name] = 'no hit box'; continue; }
    const [x, y] = at(f[0], f[1]);
    T.tapSelect(x, y, false); await new Promise(r => setTimeout(r, 60));
    const sel = C.markSel ? C.markSel.kind + ':' + (C.markSel.name || '') : (C.sel.size ? 'note' : C.selBars ? 'bar' : 'nothing');
    const del = [...document.querySelectorAll('#cpSel button')].find((b) => b.textContent.trim() === 'Delete');
    const before = JSON.stringify(S.spans) + JSON.stringify(S.measures) + JSON.stringify(st.bars) + JSON.stringify(st.clefs);
    if (del) { del.click(); await new Promise(r => setTimeout(r, 80)); }
    const S2 = C.score, st2 = S2.parts[0].staves[0];
    const after = JSON.stringify(S2.spans) + JSON.stringify(S2.measures) + JSON.stringify(st2.bars) + JSON.stringify(st2.clefs);
    out[name] = sel + (del ? (before !== after ? ' → deleted' : ' → DELETE DID NOTHING') : ' (no delete: ' + [...document.querySelectorAll('#cpSel .what')].map(x => x.textContent).join(' | ') + ')');
    if (C.markSel) { C.markSel = null; }
  }
  // bars stay whole after the deletes
  const S3 = C.score, st3 = S3.parts[0].staves[0];
  out.sums = st3.bars.every((b, m) => b.reduce((a, e) => a + M.ticksOf(e, M.timeAt(S3, m)), 0) === M.barTicks(M.timeAt(S3, m)));
  return out;
}
"""
JS2 = r"""
async () => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js');
  await E.createComposition({ title: 'Empty test', insts: ['violin', 'piano'], time: [4, 4], bars: 6 });
  await new Promise(r => setTimeout(r, 1000));
  const C = window.__compose, T = window.__composeTest, S = C.score; const all = M.allStaves(S);
  const info = M.staffInfo(S);
  C.tool.dur = 4; C.tool.dots = 0;
  for (const s of info) for (let m = 0; m < 4; m++) T.commitWrite({ staff: { st: s.st, inst: s.inst }, meas: { m }, t: 0, p: 3 });
  all[0].bars[1][0].dyn = 'f'; all[0].bars[1][0].art = ['acc']; all[1].clefs = { 2: 'bass' }; S.measures[2].rehearsal = 'B'; S.measures[1].tempo = { bpm: 100, beat: 4, text: 'Allegro' }; S.measures[3].bar = 'double';
  S.spans = [{ id: 'a', kind: 'slur', st: all[0].id, v: 1, a: { m: 0, pos: 0 }, b: { m: 1, pos: 0 } }, { id: 'b', kind: 'hairpin', st: all[1].id, v: 1, dir: '>', a: { m: 2, pos: 0 }, b: { m: 3, pos: 0 } }, { id: 'c', kind: 'ped', st: all[2].id, a: { m: 1, pos: 0 }, b: { m: 2, pos: 0 } }];
  T.selectBars(all[0], all[all.length - 1], 0, 5); T.syncSelBar();
  const empty = [...document.querySelectorAll('#cpSel button, .cp-sel-more button')].find((b) => b.textContent.trim() === 'Empty');
  empty.click(); await new Promise(r => setTimeout(r, 100));
  const S2 = C.score;
  return { notes: M.allStaves(S2).reduce((a, s) => a + s.bars.flat().filter((e) => !e.rest).length, 0), spans: (S2.spans || []).length, clefs: M.allStaves(S2).map((s) => JSON.stringify(s.clefs || {})), marks: S2.measures.map((m) => Object.keys(m).filter((k) => !['time', 'key'].includes(k)).join(',')) };
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(JS)
        for k, v in r.items(): print(f'{k:14} {v}')
        await pg.screenshot(path='/home/claude/shots/compedit.png')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        print('empty', json.dumps(await pg.evaluate(JS2)))
        print(errs); await b.close()
asyncio.run(main())
