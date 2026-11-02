# Engrave a test score with ties, slurs, staccato, accents, triplets and a trill, render it, then read it back.
import asyncio, json, sys
from playwright.async_api import async_playwright
JS = r"""
async (px) => {
  const M = await import('/js/compose/model.js'); const E = await import('/js/compose/engrave.js');
  const { loadMusicFont } = await import('/js/ink.js'); await loadMusicFont(); await document.fonts.load('100px Bravura').catch(()=>{});
  const S = M.newScore({ title: '', insts: ['violin'], time: [4, 4], bars: 4 });
  const st = S.parts[0].staves[0];
  const N = (s, t, extra = {}) => ({ id: M.newId(), t, dots: 0, notes: [{ s, a: 0, ...(extra.tie ? { tie: true } : {}) }], ...extra.ev });
  // bar 1: two tied quarter Gs, then two staccato quarters
  st.bars[0] = [N(32, 4, { tie: true }), N(32, 4), N(34, 4, { ev: { art: ['stacc'] } }), N(35, 4, { ev: { art: ['stacc'] } })];
  // bar 2: a slur over four eighths, accent on a half
  st.bars[1] = [N(30, 8), N(31, 8), N(32, 8), N(33, 8), N(35, 2, { ev: { art: ['acc'] } })];
  // bar 3: triplet eighths x2, a quarter with a trill, a quarter
  const tp = (s, i) => ({ id: M.newId(), t: 8, dots: 0, notes: [{ s, a: 0 }], tup: { n: 3, m: 2, base: 8, i } });
  st.bars[2] = [tp(30, 0), tp(31, 1), tp(32, 2), tp(33, 0), tp(34, 1), tp(35, 2), N(33, 4, { ev: { art: ['trill'] } }), N(31, 4)];
  // bar 4: a whole note
  st.bars[3] = [N(30, 1)];
  S.spans = [{ id: 's1', kind: 'slur', st: st.id, v: 1, a: { m: 1, pos: 0 }, b: { m: 1, pos: 720 } }];
  S._v2spans = 1;
  const lay = E.layoutScore(S, {});
  const sys = lay.pages[0].systems[0];
  const c = document.createElement('canvas'); const k = px;
  const top = (sys.top - 6), hgt = sys.height + 12;
  c.width = Math.round(lay.W * k); c.height = Math.round(hgt * k);
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0,0,c.width,c.height); g.scale(k, k); g.translate(0, -top); E.drawPage(g, lay, 0);
  window.__omrCanvas = c;
  if (window.__degrade) {
    const d = document.createElement('canvas'); d.width = c.width; d.height = c.height; const g2 = d.getContext('2d');
    g2.fillStyle = '#f4f1ea'; g2.fillRect(0, 0, d.width, d.height); g2.filter = 'blur(0.7px)'; g2.translate(d.width / 2, d.height / 2); g2.rotate(0.6 * Math.PI / 180); g2.translate(-d.width / 2, -d.height / 2); g2.drawImage(c, 0, 0);
    const im = g2.getImageData(0, 0, d.width, d.height); for (let i = 0; i < im.data.length; i += 4) { const n = (Math.random() - 0.5) * 50; im.data[i] += n; im.data[i+1] += n; im.data[i+2] += n; } g2.putImageData(im, 0, 0);
    c.width = d.width; c.getContext('2d').drawImage(d, 0, 0);
  }
  const O = await import('/js/omr.js');
  globalThis.__marksDbg = null; globalThis.__signDbg = []; const r = await O.recognise(c, {}); console.log(JSON.stringify(globalThis.__signDbg.filter(q => q.stacc))); const dbg = globalThis.__marksDbg; if (dbg) dbg.k = globalThis.__kdbg;
  const fmt = (it) => it.rest ? 'r' + it.t : (it.t + '.'.repeat(it.dots) + ':' + it.ps.join(',') + (it.tup ? 't' + it.tup.i : '') + (it.ties && it.ties.length ? '~' : '') + (it.slurStart ? '(' : '') + (it.slurEnd ? ')' : '') + (it.art && it.art.length ? '[' + it.art.join(',') + ']' : ''));
  let pasted = null;
  if (window.__paste) {
    const Ed = await import('/js/compose/editor.js');
    await Ed.createComposition({ insts: ['violin'], time: [4, 4], bars: 6 }); await new Promise(r => setTimeout(r, 600));
    const C = window.__compose; C.capture = { ...r, clef: r.clef || 'treble', key: r.key || 0 };
    const st = C.score.parts[0].staves[0];
    window.__composeTest.pasteCapture(st, 0);
    pasted = { bars: st.bars.slice(0, 4).map(b => b.map(e => (e.rest ? 'r' : '') + e.t + (e.tup ? 't' + e.tup.i : '') + (e.notes && e.notes.some(n => n.tie) ? '~' : '') + (e.art ? '[' + e.art + ']' : ''))), spans: (C.score.spans || []).map(q => q.kind + ' ' + q.a.m + ':' + q.a.pos + '-' + q.b.m + ':' + q.b.pos) };
    window.__composeRelayout(); await new Promise(r => setTimeout(r, 500));
  }
  return { time: r.time, bars: r.bars.map(b => b.map(fmt)), pasted, dbg, png: c.toDataURL("image/png") };
}
"""
async def main():
    px = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 16
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        if '--paste' in sys.argv: await pg.add_init_script('window.__paste = true;')
        if '--degrade' in sys.argv: await pg.add_init_script('window.__degrade = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate(JS, px)
        import base64
        open('/home/claude/shots/omr_in.png','wb').write(base64.b64decode(r.pop('png').split(',')[1]))
        if '--paste' in sys.argv: await pg.screenshot(path='/home/claude/shots/omr_paste.png')
        print(json.dumps(r)); print(errs); await b.close()
asyncio.run(main())
