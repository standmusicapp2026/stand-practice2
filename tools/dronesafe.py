import asyncio, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        await pg.add_init_script('window.__trimOne0 = ' + ('true' if '-one' in sys.argv else 'false'))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("""async (sounds) => {
          const A = await import('/js/audio.js'); const T = await import('/js/tuner.js');
          const ctx = A.getCtx(); await ctx.resume();
          // measure after the app's own limiter: find what master() feeds by tapping master and applying the same limiter
          const an = ctx.createAnalyser(); an.fftSize = 16384; an.smoothingTimeConstant = 0;
          A.master().connect(an);
          const aw = (f) => { const f2=f*f; const ra = (12194**2*f2*f2)/((f2+20.6**2)*Math.sqrt((f2+107.7**2)*(f2+737.9**2))*(f2+12194**2)); return 20*Math.log10(ra)+2.0; };
          const out = {}; if (window.__trimOne0) globalThis.__trimOne = true;
          for (const sound of sounds) for (const oct of [1,2,3,4,5,6]) {
            const d = new T.Drone(); d.sound = sound; d.volume = 1; d.octave = oct; d.pc = 9; d.chord = 'fifth';
            d.start(); await new Promise(r=>setTimeout(r,1400));
            const buf = new Float32Array(an.fftSize); an.getFloatTimeDomainData(buf);
            let s=0,pk=0; for (const x of buf) { s+=x*x; pk=Math.max(pk,Math.abs(x)); }
            const fd = new Float32Array(an.frequencyBinCount); an.getFloatFrequencyData(fd);
            let pa=0; const bw = ctx.sampleRate/an.fftSize; for (let i=1;i<fd.length;i++){ pa += Math.pow(10,(fd[i]+aw(i*bw))/10); }
            let pz=0; for (let i=1;i<fd.length;i++) pz += Math.pow(10,fd[i]/10);
            out[sound+' A'+oct] = [ (20*Math.log10(Math.sqrt(s/buf.length))).toFixed(1), (20*Math.log10(pk)).toFixed(1), (10*Math.log10(pa/pz)+20*Math.log10(Math.sqrt(s/buf.length))).toFixed(1) ];
            d.stop(); await new Promise(r=>setTimeout(r,400));
          }
          return out; }""", (sys.argv[1] if len(sys.argv)>1 else 'pure,organ').split(','))
        for k,v in r.items(): print(f"{k:10s} rms {v[0]:>6} peak {v[1]:>6} A-weighted {v[2]:>6}")
        await b.close()
asyncio.run(main())
