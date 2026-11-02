# What kind of sound is said to iOS (navigator.audioSession, mocked): playback for the metronome,
# play-and-record while the tuner listens, back to playback after; play-and-record with the speaker kept
import asyncio, os
from playwright.async_api import async_playwright
MOCK = "window.standCaps = { native: true }; window.__types = []; Object.defineProperty(navigator, 'audioSession', { value: { _t: 'auto', get type() { return this._t; }, set type(v) { this._t = v; window.__types.push(v); } } });"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])
        pg = await (await b.new_context(permissions=['microphone'])).new_page()
        await pg.add_init_script('window.__noTour = true;' + MOCK); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate("""async () => { const sleep = (ms) => new Promise(r => setTimeout(r, ms)); const out = {};
          const M = await import('/js/metronome.js'); const met = new M.Metronome(); met.start(); await sleep(300); out.metro = navigator.audioSession.type;
          const T = await import('/js/tuner.js'); const tn = new T.Tuner(); await tn.start(); await sleep(1500); out.tuner = navigator.audioSession.type;
          tn.stop(); await sleep(1500); out.after = navigator.audioSession.type; met.stop();
          window.__standSpeaker = true; (await import('/js/audio.js')).applySession(); out.speaker = navigator.audioSession.type;
          return { ...out, all: window.__types }; }""")
        print(r, errs[:3]); await b.close()
asyncio.run(main())
