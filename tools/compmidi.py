import asyncio, json, os, base64, io, struct
from playwright.async_api import async_playwright
JS = r"""
async () => {
  const M = await import('/js/compose/model.js'), X = await import('/js/compose/midi.js');
  const sc = M.newScore({ title: 'Midi test', insts: ['violin', 'piano'], bars: 4 });
  const st = sc.parts[0].staves[0];
  st.bars[0] = [1,2,3,4].map((k) => ({ id: M.newId(), t: 4, dots: 0, notes: [{ s: 30 + k, a: 0 }], ...(k === 3 ? { txt: 'pizz.', txtStyle: 'tech' } : {}) }));
  sc.measures[1].bar = 'repeat';
  const b = X.toMidi(sc); const buf = new Uint8Array(await b.arrayBuffer());
  let s = ''; for (const x of buf) s += String.fromCharCode(x); return btoa(s);
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        data = base64.b64decode(await pg.evaluate(JS))
        def rd(d):
            assert d[:4] == b'MThd'; fmt, ntr, ppq = struct.unpack('>HHH', d[8:14]); i = 14; out = []
            for _ in range(ntr):
                assert d[i:i+4] == b'MTrk', d[i:i+4]; ln = struct.unpack('>I', d[i+4:i+8])[0]; tr = d[i+8:i+8+ln]; i += 8 + ln
                j = 0; t = 0; ev = []; run = None
                while j < len(tr):
                    v = 0
                    while True:
                        c = tr[j]; j += 1; v = (v << 7) | (c & 127)
                        if c < 128: break
                    t += v; st = tr[j]
                    if st == 0xff:
                        ty = tr[j+1]; j += 2; l = 0
                        while True:
                            c = tr[j]; j += 1; l = (l << 7) | (c & 127)
                            if c < 128: break
                        ev.append((t, 'meta', ty, tr[j:j+l])); j += l
                    else:
                        j += 1; hi = st & 0xf0; n = 1 if hi in (0xc0, 0xd0) else 2
                        ev.append((t, hex(hi), tr[j:j+n])); j += n
                out.append(ev)
            return fmt, ppq, out
        fmt, ppq, trs = rd(data)
        print('type', fmt, 'ppq', ppq, 'tracks', len(trs))
        for ev in trs: print(len([e for e in ev if e[1] == '0x90']), 'notes, programs', [e[2][0] for e in ev if e[1] == '0xc0'], 'end tick', ev[-1][0])
        print(errs); await b.close()
asyncio.run(main())
