# The strings' dynamics: each note's loudness from pp to ff (each dynamic over a rising scale), and
# how much notes of the same dynamic differ from each other (no sudden jumps)
import asyncio, json, os
from playwright.async_api import async_playwright
JS = r"""
async (inst) => {
  const E = await import('/js/compose/editor.js'); const M = await import('/js/compose/model.js'); const P = await import('/js/compose/playback.js');
  const dyns = ['pp', 'p', 'mp', 'mf', 'f', 'ff'];
  await E.createComposition({ title: 'Dyn', insts: [inst], time: [4, 4], bars: dyns.length * 2 });
  await new Promise(r => setTimeout(r, 800));
  const C = window.__compose, T = window.__composeTest, st = M.staffInfo(C.score)[0];
  const base = inst === 'violin' ? 30 : 16;
  C.tool.dur = 4;
  for (let m = 0; m < dyns.length * 2; m++) for (let t = 0; t < 4; t++) T.commitWrite({ staff: { st: st.st, inst: st.inst }, meas: { m }, t: t * 480, p: base + ((m % 2) * 4 + t) - 8 });
  const bars = C.score.parts[0].staves[0].bars;
  dyns.forEach((d, i) => { bars[i * 2][0].dyn = d; });
  C.score.sound = { ...(C.score.sound || {}), style: 'straight', human: false };
  const blob = await P.renderAudio(C.score);
  const v = new DataView(await blob.arrayBuffer()); const sr = v.getUint32(24, true), bits = v.getUint16(34, true), ch = v.getUint16(22, true);
  const n = (v.byteLength - 44) / (ch * bits / 8); const L = new Float32Array(n);
  for (let i = 0; i < n; i++) { const o = 44 + i * ch * 3; let x = v.getUint8(o) | (v.getUint8(o + 1) << 8) | (v.getInt8(o + 2) << 16); L[i] = x / 8388607; }
  const tl = P.buildTimeline(C.score, { humanize: false });
  const out = tl.notes.filter(q => q.part === C.score.parts[0].id).map((q) => { const a = Math.floor((0.2 + q.t + 0.08) * sr), b = Math.floor((0.2 + q.t + Math.min(q.dur * 0.8, 0.45)) * sr); let s = 0; for (let i = a; i < b; i++) s += L[i] * L[i]; return { m: q.m, vel: +q.vel.toFixed(2), db: +(10 * Math.log10(s / Math.max(1, b - a) + 1e-12)).toFixed(1) }; });
  return out;
}
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }"); await pg.wait_for_timeout(500)
        for inst in ['cello', 'violin']:
            r = await pg.evaluate(JS, inst)
            dyns = ['pp', 'p', 'mp', 'mf', 'f', 'ff']; rows = []
            for k, d in enumerate(dyns):
                vals = [x['db'] for x in r if x['m'] in (2 * k, 2 * k + 1)]
                if not vals: continue
                rows.append(f"{d}: mean {sum(vals)/len(vals):.1f} spread {max(vals)-min(vals):.1f}")
            steps = [round(r[i+1]['db'] - r[i]['db'], 1) for i in range(len(r) - 1)]
            print(inst, ' | '.join(rows)); print('  biggest jump between neighbouring notes', max(steps, key=abs), 'vels', sorted(set(x['vel'] for x in r))[:3], '...')
        print(errs[:3]); await b.close()
asyncio.run(main())
