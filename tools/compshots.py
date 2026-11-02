# Compose: pages of a few typical scores drawn as pictures, to look at the spacing
import asyncio, os, sys, base64
from playwright.async_api import async_playwright
OUT = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/cs/' + (sys.argv[1] if len(sys.argv) > 1 else 'now')
JS = """async () => {
  const M = await import('/js/compose/model.js'), E = await import('/js/compose/engrave.js'), I = await import('/js/ink.js');
  try { await I.loadMusicFont(); } catch {}
  try { await document.fonts.load('80px Bravura'); } catch {}
  const rnd = ((s) => () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; })(7);
  const fill = (score, st, base, kind) => {
    const time = [4, 4];
    for (let m = 0; m < score.measures.length; m++) {
      const bar = []; let left = 1920;
      while (left > 0) {
        let t = kind === 'q' ? (rnd() < 0.7 ? 8 : 4) : kind === 'h' ? (rnd() < 0.5 ? 2 : 4) : 4; let tk = 1920 / t; if (tk > left) { t = 1920 / left; tk = left; }
        const s = base + Math.floor(rnd() * 9) - 2;
        const notes = kind === 'h' ? [{ s, a: 0 }, { s: s + 2, a: 0 }, { s: s + 4, a: 0 }] : [{ s, a: rnd() < 0.1 ? 1 : 0 }];
        bar.push({ id: M.newId(), t, dots: 0, notes }); left -= tk;
      }
      st.bars[m] = bar;
    }
  };
  const out = {};
  const mk = (name, insts, bars, fills) => { const sc = M.newScore({ title: name, composer: 'Test', insts, bars }); const sts = M.allStaves(sc); fills.forEach((f, i) => sts[i] && f && fill(sc, sts[i], f[0], f[1])); return sc; };
  const scores = {
    solo: mk('Violin solo', ['violin'], 40, [[30, 'q']]),
    duo: mk('Sonata', ['violin', 'piano'], 32, [[30, 'q'], [28, 'h'], [16, 'n']]),
    quartet: mk('Quartet', ['violin', 'violin', 'viola', 'cello'], 24, [[30, 'q'], [28, 'n'], [24, 'n'], [16, 'q']]),
  };
  for (const [k, sc] of Object.entries(scores)) {
    const lay = E.layoutScore(sc);
    const pxPerSp = 1240 / lay.W;
    for (let p = 0; p < Math.min(2, lay.pages.length); p++) {
      const c = document.createElement('canvas'); c.width = Math.round(lay.W * pxPerSp); c.height = Math.round(lay.H * pxPerSp);
      const g = c.getContext('2d'); g.scale(pxPerSp, pxPerSp); E.drawPage(g, lay, p);
      out[k + p] = c.toDataURL('image/png');
    }
    out[k + '_info'] = { pages: lay.pages.length, sp: lay.spMm, sys: lay.pages.map((pg) => pg.systems.map((s) => +s.top.toFixed(1))), margin: lay.margin, x: lay.pages[0].systems.map((s) => [+s.x0.toFixed(1), +s.x1.toFixed(1)]) };
  }
  return out;
}"""
async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(JS)
        for k, v in r.items():
            if k.endswith('_info'): print(k, v); continue
            open(f'{OUT}/{k}.png', 'wb').write(base64.b64decode(v.split(',')[1]))
        print(errs[:3]); await b.close()
asyncio.run(main())
