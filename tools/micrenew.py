# The microphone opened while the metronome plays: the sound renewed once, metronome and tuner go on
import asyncio, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, permissions=['microphone'])).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append('pageerror ' + str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const A = await import('/js/audio.js'); " + js + " }")
        r = await J("""const M = await import('/js/metronome.js'); const met = new M.Metronome(); met.start(); await sleep(500);
          const n0 = window.__audioLog.filter(e => /new sound/.test(e.what)).length;
          const T = await import('/js/tuner.js'); const tn = new T.Tuner(); await tn.start(); await sleep(3000);
          const n1 = window.__audioLog.filter(e => /new sound/.test(e.what)).length;
          const mid = { metro: met.running && met._ctx === A.getCtx(), tunerCtx: tn.analyser.context === A.getCtx(), tunerOn: tn.running, readings: (tn.onReading = null, 0) };
          tn.stop(); await sleep(3000);
          const n2 = window.__audioLog.filter(e => /new sound/.test(e.what)).length;
          const end = { metro: met.running && met._ctx === A.getCtx() }; met.stop();
          return { renewOpen: n1 - n0, renewClose: n2 - n1, mid, end, log: window.__audioLog.slice(-10).map(e => e.what) };""")
        print(r)
        print('errors', errs[:6]); await b.close()
asyncio.run(main())
