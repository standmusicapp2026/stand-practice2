import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); pg = await (await b.new_context()).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("""async () => {
          const A = await import('/js/audio.js'); const T = await import('/js/tuner.js');
          const out = [];
          const level = async () => { const c = A.getCtx(); const an = c.createAnalyser(); an.fftSize=4096; A.master().connect(an); await new Promise(r=>setTimeout(r,500)); const b=new Float32Array(4096); an.getFloatTimeDomainData(b); let s=0; for(const x of b) s+=x*x; return +(20*Math.log10(Math.sqrt(s/4096)+1e-9)).toFixed(1); };
          const d = new T.Drone(); d.octave = 3; d.start();
          const c1 = A.getCtx(); out.push(['playing', await level()]);
          window.standAudioWake('route');
          await new Promise(r=>setTimeout(r,1800));
          const c2 = A.getCtx(); out.push(['after route while playing: new ctx', c1 !== c2, c1.state, c2.state, await level()]);
          d.stop(); await new Promise(r=>setTimeout(r,800));
          window.standAudioWake('route'); await new Promise(r=>setTimeout(r,700));
          d.start(); const c3 = A.getCtx(); out.push(['idle route then start: new ctx', c3 !== c2, c2.state, await level()]);
          d.stop(); return out; }""")
        for x in r: print(x)
        print(errs)
        await b.close()
asyncio.run(main())
