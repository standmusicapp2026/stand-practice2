# Compose: the new markings drawn (64ths, double dots, reminder accidentals, strings, fingering for
# chords, line and page breaks, new dynamics, dotted-quarter tempo), and played (pizz./arco)
import asyncio, os, base64, json
from playwright.async_api import async_playwright
OUT = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/cs/feat'
JS = """async () => {
  const M = await import('/js/compose/model.js'), E = await import('/js/compose/engrave.js'), I = await import('/js/ink.js'), P = await import('/js/compose/playback.js');
  try { await I.loadMusicFont(); } catch {}
  const sc = M.newScore({ title: 'Features', insts: ['violin'], bars: 12, time: [6, 8] });
  sc.measures[0].tempo = { bpm: 60, beat: 4, dotted: true, text: 'Andante' };
  const st = sc.parts[0].staves[0];
  const N = (t, s, extra = {}) => ({ id: M.newId(), t, dots: 0, notes: [{ s, a: 0 }], ...extra });
  st.bars[0] = [N(64, 32), N(64, 33), N(64, 34), N(64, 35), N(32, 36), N(16, 37), { ...N(4, 38), dots: 2 }, N(64, 37), N(64, 36)].slice(0, 9);
  st.bars[0] = [N(64, 32), N(64, 33), N(64, 34), N(64, 35), N(32, 36), N(16, 37), N(8, 38), { ...N(4, 34), dots: 1 }];
  st.bars[1] = [{ ...N(4, 33), dots: 1, notes: [{ s: 33, a: 0, cau: true }] }, { ...N(4, 31), dots: 1, str: 'II', fing: '1 3', notes: [{ s: 31, a: 0 }, { s: 35, a: 0 }] }];
  st.bars[2] = [{ ...N(4, 30), dots: 1, dyn: 'sffz', txt: 'pizz.', txtStyle: 'tech' }, { ...N(4, 32), dots: 1, dyn: 'sfp' }];
  st.bars[3] = [{ ...N(4, 33), dots: 1, txt: 'arco', txtStyle: 'tech', dyn: 'pppp' }, { ...N(4, 34), dots: 1, dyn: 'ffff', str: 'IV' }];
  sc.measures[2].brk = 'sys'; sc.measures[6].brk = 'page';
  const lay = E.layoutScore(sc);
  const out = { pages: lay.pages.length, lines: lay.pages.map((p) => p.systems.map((s) => s.measures.map((x) => x.m + 1).join(','))) };
  const px = 1240 / lay.W;
  out.imgs = [];
  for (let p = 0; p < lay.pages.length; p++) { const c = document.createElement('canvas'); c.width = Math.round(lay.W * px); c.height = Math.round(lay.H * px); const g = c.getContext('2d'); g.scale(px, px); E.drawPage(g, lay, p); out.imgs.push(c.toDataURL('image/png')); }
  const tl = P.buildTimeline ? P.buildTimeline(sc, { expr: true }) : null;
  if (tl) out.sids = [...new Set(tl.notes.map((n) => n.m + ':' + n.sid))];
  const X = await import('/js/compose/musicxml.js'); const xml = X.toMusicXML ? X.toMusicXML(sc) : X.exportMusicXML ? X.exportMusicXML(sc) : '';
  out.xml = { str: /<string>2<\\/string>/.test(xml), cau: /cautionary="yes"/.test(xml), len: xml.length };
  return out;
}"""
async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(JS)
        for i, v in enumerate(r.pop('imgs')): open(f'{OUT}/p{i}.png', 'wb').write(base64.b64decode(v.split(',')[1]))
        print(json.dumps(r)); print(errs[:3]); await b.close()
asyncio.run(main())
