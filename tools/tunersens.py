import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("""async () => {
          const T = await import('/js/tuner.js'); const sr = 48000, N = 2048;
          const tone = (f, amp, ph) => { const b = new Float32Array(N); for (let i = 0; i < N; i++) { const t = (ph + i) / sr; let v = 0; for (let k = 1; k <= 6; k++) v += Math.sin(2 * Math.PI * f * k * t) / k; b[i] = v * amp * 0.6 + (Math.random() * 2 - 1) * 0.0004; } return b; };
          const res = {};
          for (const amp of [0.001, 0.002, 0.004, 0.01, 0.05]) {
            const tr = new T.PitchTracker(); let ok = 0, n = 0, first = -1;
            for (let i = 0; i < 60; i++) { const buf = tone(130.81, amp, i * 800); let ms = 0; for (const v of buf) ms += v * v; const rms = Math.sqrt(ms / N); const d = T.detectPitch(buf, sr, 0.00035); const o = tr.feed(d, rms, i * 16.7); n++; if (o && Math.abs(1200 * Math.log2(o.f / 130.81)) < 15) { ok++; if (first < 0) first = i; } }
            res['amp ' + amp] = { okFrames: ok + '/' + n, firstFrame: first };
          }
          // silence with room noise: no false notes
          { const tr = new T.PitchTracker(); let falseN = 0; for (let i = 0; i < 120; i++) { const b = new Float32Array(N); for (let k = 0; k < N; k++) b[k] = (Math.random() * 2 - 1) * 0.0006; let ms = 0; for (const v of b) ms += v * v; const o = tr.feed(T.detectPitch(b, sr, 0.00035), Math.sqrt(ms / N), i * 16.7); if (o && !o.held) falseN++; } res.noiseFalse = falseN; }
          return res; }""")
        for k,v in r.items(): print(k, v)
        await b.close()
asyncio.run(main())
