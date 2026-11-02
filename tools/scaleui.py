import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']); pg = await (await b.new_context()).new_page()
        await pg.add_init_script('window.__noTour = true;')
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }")
        r = await pg.evaluate("""async () => {
          const A = await import('/js/audio.js'); const sleep = (ms) => new Promise(r => setTimeout(r, ms));
          const level = async () => { const c = A.getCtx(); const an = c.createAnalyser(); an.fftSize = 4096; A.master().connect(an); let mx = 0; for (let i = 0; i < 15; i++) { await sleep(60); const d = new Float32Array(4096); an.getFloatTimeDomainData(d); for (const v of d) mx = Math.max(mx, Math.abs(v)); } return +mx.toFixed(3); };
          document.querySelector('.tile[data-tile="scales"]').click(); await sleep(500);
          document.querySelector('#scaleToggle').click(); await sleep(2600);
          const a = await level();
          await A.healAudio('reset'); await sleep(1500);
          const b = await level();
          document.querySelector('#scaleToggle').click(); await sleep(300);
          return { before: a, afterRebuild: b, stopped: !document.querySelector('#scalePill') || document.querySelector('#scalePill').hidden };
        }""")
        print(r, errs); await b.close()
asyncio.run(main())
