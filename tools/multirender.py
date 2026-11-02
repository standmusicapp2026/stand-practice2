# Render a list of notes for several instruments through the app's sampler (no score engine): JSON in,
# WAV out. notes: [{sid, kind, midi, t, dur, vel}] ; env G sets globals.
import asyncio, json, os, sys, base64
from playwright.async_api import async_playwright
JS = r"""
async (notes) => {
  const S = await import('/js/sampler.js');
  const sampler = S.sampler; sampler.live();
  await sampler.prepare(notes.map((n) => ({ sid: n.sid, midi: n.midi, kind: n.kind, vel: n.vel })));
  const total = Math.max(...notes.map((n) => n.t + n.dur)) + 6, sr = 48000;
  const off = new OfflineAudioContext(2, Math.ceil(total * sr), sr);
  const s2 = new S.Sampler(); s2.buffers = sampler.buffers; s2.attach(off, off.destination);
  s2.setRoom(globalThis.__room || 'hall'); s2.setRoomMix(globalThis.__rmix ?? 1);
  const chans = {};
  const one = async (n) => {
    const key = n.ch || n.sid;
    if (!chans[key]) chans[key] = s2.channel(key, n.sid, { ...S.DEFAULT_MIX(), ...(n.mix || {}) });
    const smp = await s2.sampleFor(n.sid, n.midi, n.kind || 'sus', n.vel, n.opts && n.opts.env ? [n.vel, ...n.opts.env.map((e) => n.vel * e[1])] : null).catch(() => null);
    s2.noteOn(chans[key], smp, n.midi, 0.2 + n.t, n.dur, n.vel, n.opts || {});
  };
  const ns = notes.slice().sort((a, b) => a.t - b.t), BLOCK = 4; let i = 0;
  const addUntil = async (tEnd) => { while (i < ns.length && 0.2 + ns[i].t < tEnd) await one(ns[i++]); };
  await addUntil(BLOCK);
  for (let b = 1; b * BLOCK < total; b++) off.suspend(b * BLOCK - 0.5).then(async () => { await addUntil((b + 1) * BLOCK); off.resume(); });
  const buf = await off.startRendering();
  const W = await import('/js/recorder.js'); const blob = W.encodeWav([buf.getChannelData(0), buf.getChannelData(1)], sr, 24);
  const u = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
  return btoa(s);
}
"""
async def main():
    notes = json.load(open(sys.argv[1]))
    if os.environ.get('WIN'):
        t0, t1 = map(float, os.environ['WIN'].split(','))
        notes = [dict(n, t=round(n['t'] - t0, 4)) for n in notes if t0 <= n['t'] < t1]
    if os.environ.get('ONLY'):
        keep = set(os.environ['ONLY'].split(',')); notes = [n for n in notes if n['sid'] in keep]
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate(JS, notes)
        open(sys.argv[2], 'wb').write(base64.b64decode(r))
        if errs: print('ERR', errs[:3])
        await b.close()
asyncio.run(main())
