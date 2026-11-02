# Compose sound: a violin and cello passage rendered (held, staccato, pizz., tremolo, soft and loud);
# which recordings were used, the level of each part, and the WAV kept to listen to
import asyncio, os, base64, json
from playwright.async_api import async_playwright
OUT = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/snd'
JS = r"""async (plain) => {
  const M = await import('/js/compose/model.js'), P = await import('/js/compose/playback.js'), S = await import('/js/sampler.js');
  S.Sampler.prototype.plain = !!plain;
  const sc = M.newScore({ title: 'Sound', insts: ['violin', 'cello'], bars: 6, bpm: 84 }); sc.sound.plainStrings = !!plain;
  const [vl, vc] = [sc.parts[0].staves[0], sc.parts[1].staves[0]];
  const N = (t, s, x = {}) => ({ id: M.newId(), t, dots: 0, notes: [{ s, a: 0 }], ...x });
  vl.bars[0] = [N(2, 33, { dyn: 'p' }), N(2, 35)];
  vl.bars[1] = [N(8, 36, { art: ['stacc'], dyn: 'f' }), N(8, 35, { art: ['stacc'] }), N(8, 34, { art: ['stacc'] }), N(8, 33, { art: ['stacc'] }), N(2, 32)];
  vl.bars[2] = [N(4, 31, { txt: 'pizz.', txtStyle: 'tech', dyn: 'mf' }), N(4, 33), N(4, 35), N(4, 37)];
  vl.bars[3] = [N(1, 36, { txt: 'arco', txtStyle: 'tech', art: ['trem3'], dyn: 'pp' })];
  vl.bars[4] = [N(1, 37, { dyn: 'ff' })];
  vc.bars[0] = [N(1, 21, { dyn: 'mp' })]; vc.bars[1] = [N(1, 19)]; vc.bars[2] = [N(2, 17, { dyn: 'f' }), N(2, 21)]; vc.bars[3] = [N(1, 14, { dyn: 'p' })]; vc.bars[4] = [N(1, 16)];
  const tl = P.buildTimeline(sc, {});
  const kinds = {}; for (const n of tl.notes) { const k = n.sid + ':' + (n.kind || '-'); kinds[k] = (kinds[k] || 0) + 1; }
  const blob = await P.renderAudio(sc);
  const ab = await blob.arrayBuffer(); const d = new DataView(ab);
  // 16-bit stereo after a 44-byte header: the level of each bar (dB)
  const sr = 44100, n = (ab.byteLength - 44) / 4, bar = Math.round(sr * 60 / 84 * 4), lv = [];
  let peak = 0;
  for (let b = 0; b < 6; b++) { let s2 = 0, c = 0; for (let i = b * bar + Math.round(sr * 0.2); i < Math.min(n, (b + 1) * bar); i++) { const v = d.getInt16(44 + i * 4, true) / 32768; s2 += v * v; c++; peak = Math.max(peak, Math.abs(v)); } lv.push(c ? +(10 * Math.log10(s2 / c + 1e-12)).toFixed(1) : null); }
  let s = ''; const u = new Uint8Array(ab); for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768));
  return { kinds, lv, peak: +peak.toFixed(2), wav: btoa(s) };
}"""
async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        for plain in (True, False):
            r = await pg.evaluate(JS, plain)
            open(f"{OUT}/{'old' if plain else 'new'}.wav", 'wb').write(base64.b64decode(r.pop('wav')))
            print('old' if plain else 'new', json.dumps(r))
        print(errs[:4]); await b.close()
asyncio.run(main())
