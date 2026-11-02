import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' and 'TUNNEL' not in m.text and 'peerjs' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("""async () => {
          const { getCtx, master } = await import('/js/audio.js'); const S = await import('/js/scales.js');
          const ctx = getCtx(); await ctx.resume(); const an = ctx.createAnalyser(); an.fftSize = 8192; master().connect(an);
          const out = {};
          for (const sound of ['piano', 'organ', 'bow', 'pure']) {
            const sp = new S.ScalePlayer(); sp.sound = sound; sp.countIn = false; sp.bpm = 120; sp.start();
            let mx = 0; for (let i = 0; i < 20; i++) { await new Promise(r => setTimeout(r, 50)); const d = new Float32Array(an.fftSize); an.getFloatTimeDomainData(d); for (const v of d) mx = Math.max(mx, Math.abs(v)); }
            sp.stop(); out[sound] = +mx.toFixed(3); await new Promise(r => setTimeout(r, 300));
          }
          return out; }""")
        print(r, errs); await b.close()
asyncio.run(main())
