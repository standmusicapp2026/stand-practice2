# The drone through its way out: loudness (RMS, dB) and the peak, with the old saturation and clean
import asyncio, os, json, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1000)
        res = await pg.evaluate("""async (mks) => {
          const T = await import('/js/tuner.js'); const A = await import('/js/audio.js');
          const ctx = A.getCtx(); await ctx.resume(); const an = ctx.createAnalyser(); an.fftSize = 32768; A.master().connect(an);
          const buf = new Float32Array(an.fftSize); const sleep = (ms) => new Promise(r => setTimeout(r, ms)); const out = [];
          const measure = async () => { let s = 0, n = 0, pk = 0; for (let k = 0; k < 6; k++) { await sleep(180); an.getFloatTimeDomainData(buf); for (const v of buf) { s += v * v; pk = Math.max(pk, Math.abs(v)); } n += buf.length; } return [+(10 * Math.log10(s / n)).toFixed(1), +pk.toFixed(2)]; };
          for (const [sat, mk] of mks) {
            globalThis.__droneSat = sat; globalThis.__droneMk = mk;
            const row = { sat, mk };
            for (const [sound, oct, chord] of [['organ', 2, 'fifth'], ['bow', 3, 'fifth'], ['horn', 2, 'octave'], ['pure', 3, 'fifth'], ['organ', 4, 'root']]) {
              const d = new T.Drone(); d.sound = sound; d.octave = oct; d.chord = T.DRONE_CHORDS && T.DRONE_CHORDS[chord] ? chord : 'fifth'; d.volume = 1; d.start(); await sleep(900);
              row[sound + oct + chord] = await measure(); d.stop(); await sleep(400);
            }
            out.push(row);
          }
          return out; }""", json.loads(sys.argv[1]))
        for r in res: print(json.dumps(r))
        print(errs[:3]); await b.close()
asyncio.run(main())
