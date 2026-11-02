import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']); pg = await (await b.new_context(permissions=['microphone'])).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script('window.__noTour = true;')
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("""async () => {
          const A = await import('/js/audio.js'); const T = await import('/js/tuner.js');
          const sleep = (ms) => new Promise(r=>setTimeout(r,ms));
          const level = async () => { const c = A.getCtx(); const an = c.createAnalyser(); an.fftSize=4096; A.master().connect(an); await sleep(500); const b=new Float32Array(4096); an.getFloatTimeDomainData(b); let s=0; for(const x of b) s+=x*x; return +(20*Math.log10(Math.sqrt(s/4096)+1e-9)).toFixed(1); };
          const out = [];
          // 1. a stuck suspended sound system: resume does nothing
          const c1 = A.getCtx(); await c1.suspend(); c1.resume = () => Promise.resolve();
          const d = new T.Drone(); d.octave = 3; d.start();
          await sleep(1500);
          const c2 = A.getCtx(); out.push(['stuck suspended -> replaced', c1 !== c2, c2.state, d.running, await level()]);
          d.stop(); await sleep(300);
          // 2. after the microphone was used and let go, the drone gets a fresh one
          await A.acquireMic(); await sleep(300); A.releaseMic();
          const c3 = A.getCtx(); d.start(); const c4 = A.getCtx();
          out.push(['after mic -> fresh', c3 !== c4, c4.state, await level()]);
          d.stop();
          return out; }""")
        for x in r: print(x)
        print(errs); await b.close()
asyncio.run(main())
