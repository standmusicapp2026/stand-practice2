# Play a MIDI file (notes, velocities, sustain pedal) through the app's own sampler -> WAV.
# usage: midirender.py in.mid out.wav [sid=piano] ; env G='{"__x":1}' sets globals first
import asyncio, json, os, sys, base64, mido
from playwright.async_api import async_playwright
def notes_of(path):
    mf = mido.MidiFile(path); t = 0; on = {}; out = []; ped = False; held = []  # held: notes released while pedal down
    events = []
    for msg in mf:
        t += msg.time
        events.append((t, msg))
    for t, msg in events:
        if msg.type == 'note_on' and msg.velocity > 0: on[(msg.channel, msg.note)] = (t, msg.velocity)
        elif msg.type in ('note_off', 'note_on'):
            k = (msg.channel, msg.note)
            if k in on:
                t0, v = on.pop(k); n = {'midi': msg.note, 't': t0, 'off': t, 'vel': v}
                out.append(n)
                if ped: held.append(n)
        elif msg.type == 'control_change' and msg.control == 64:
            if msg.value >= 64: ped = True
            elif ped:
                ped = False
                for n in held: n['off'] = max(n['off'], t)
                held = []
    for n in out: n['dur'] = max(0.03, n['off'] - n['t'])
    return sorted(out, key=lambda n: n['t'])
JS = r"""
async ([notes, sid]) => {
  const S = await import('/js/sampler.js');
  const sampler = S.sampler; sampler.live();
  await sampler.prepare(notes.map((n) => ({ sid, midi: n.midi, kind: 'sus', vel: n.vel / 127 })));
  const total = Math.max(...notes.map((n) => n.t + n.dur)) + 6, sr = 48000;
  const off = new OfflineAudioContext(2, Math.ceil(total * sr), sr);
  const s2 = new S.Sampler(); s2.buffers = sampler.buffers; s2.attach(off, off.destination);
  s2.setRoom(globalThis.__room || 'hall'); s2.setRoomMix(globalThis.__rmix ?? 1);
  const ch = s2.channel('p', sid, S.DEFAULT_MIX());
  for (const n of notes) { const smp = await s2.sampleFor(sid, n.midi, 'sus', n.vel / 127).catch(() => null); s2.noteOn(ch, smp, n.midi, 0.2 + n.t, n.dur, n.vel / 127, {}); }
  const buf = await off.startRendering();
  const L = buf.getChannelData(0), R = buf.getChannelData(1);
  const W = await import('/js/recorder.js'); const blob = W.encodeWav([L, R], sr, 24);
  const u = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
  return btoa(s);
}
"""
async def main():
    notes = notes_of(sys.argv[1]); sid = sys.argv[3] if len(sys.argv) > 3 else 'piano'
    print(len(notes), 'notes', round(notes[-1]['t'], 1), 's')
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        if os.environ.get('G'): await pg.evaluate('(g) => Object.assign(globalThis, JSON.parse(g))', os.environ['G'])
        r = await pg.evaluate(JS, [notes, sid])
        open(sys.argv[2], 'wb').write(base64.b64decode(r))
        if errs: print('ERR', errs[:3])
        await b.close()
if __name__ == "__main__": asyncio.run(main())
