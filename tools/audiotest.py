# The sound system replaced (Bluetooth on or off, a call) while things play, and recording after it:
# everything must go on, with no errors
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, permissions=['microphone'])).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append('pageerror ' + str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const A = await import('/js/audio.js'); " + js + " }")
        state = "return { n: window.__audioLog.filter(e => /new sound/.test(e.what)).length, state: A.getCtx().state, log: window.__audioLog.slice(-4).map(e => e.what) }"
        # 1. record a take, play it, replace the sound system while it plays, record again
        r = await J("""const R = await import('/js/recorder.js'); const rec = new R.Recorder(); await rec.prepare(); rec.start(); await sleep(800); const t1 = await rec.stop();
          const pl = new R.Player(); pl.load({ data: t1.data, sr: t1.sr, peak: 0.5 }); await pl.play(); await sleep(300);
          window.standAudioWake('route-change'); await sleep(1500);
          const after = { playing: pl.playing, pos: +pl.currentPos().toFixed(2), sameCtx: pl.out && pl.out.context === A.getCtx() };
          pl.stop();
          const rec2 = new R.Recorder(); await rec2.prepare(); rec2.start(); await sleep(600); const t2 = await rec2.stop();
          return { take1: t1.data.length, sr1: t1.sr, after, take2: t2.data.length, sr2: t2.sr };""")
        print('recorder', r, await J(state))
        # 2. a route change made by the microphone itself: kept, not replaced
        n0 = (await J(state))['n']
        await J("const T = await import('/js/tuner.js'); window.__tn = new T.Tuner(); await window.__tn.start(); await sleep(200); window.standAudioWake('route-change'); await sleep(1500);")
        print('route from the microphone opening: new sound systems', (await J(state))['n'] - n0, (await J(state))['log'])
        await J("window.__tn.stop(); await sleep(3500);")
        # 3. metronome, drone, scales and compose playing; a real new device: replaced once, all go on
        n0 = (await J(state))['n']
        r = await J("""const M = await import('/js/metronome.js'); const met = new M.Metronome(); met.start(); await sleep(400);
          window.standAudioWake('route-bluetooth'); await sleep(1600);
          const ok = met.running && met._ctx === A.getCtx();
          window.standAudioWake('route-bluetooth'); await sleep(200); window.standAudioWake('route-bluetooth'); await sleep(1500);
          met.stop(); return { metroOn: ok };""")
        print('metronome through a new device', r, 'new sound systems', (await J(state))['n'] - n0)
        await J("await A.resetSound(); await sleep(300);")
        print('reset by hand', await J(state))
        print('record after new sound systems', await J("const R = await import('/js/recorder.js'); const rec = new R.Recorder(); await rec.prepare(); rec.start(); await sleep(600); const t = await rec.stop(); const pl = new R.Player(); pl.load({ data: t.data, sr: t.sr, peak: 0.5 }); await pl.play(); await sleep(100); const was = pl.playing; await A.resetSound(); await sleep(400); return { len: t.data.length, playingAfterReset: pl.playing, was };"))
        print('errors', errs[:6]); await b.close()
asyncio.run(main())
