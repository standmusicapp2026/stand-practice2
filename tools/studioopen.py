# Studio opening from a recording: never the main screen in between, a failing score tried again,
# a Studio that cannot open leaves you on the recording, Back comes back to the recording.
import asyncio, base64, os, sys
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765'); BR = os.environ.get('BR', 'chromium')
VIEWS = [('ipad', 1180, 820), ('iphone', 390, 844), ('iphone-land', 844, 390)]
async def main():
    fails = []
    def check(c, m):
        print(('ok   ' if c else 'FAIL ') + m)
        if not c: fails.append(m)
    async with async_playwright() as p:
        bt = getattr(p, BR)
        b = await bt.launch(**({'args': ['--autoplay-policy=no-user-gesture-required']} if BR == 'chromium' else {}))
        for name, w, h in VIEWS:
            ctx = await b.new_context(viewport={'width': w, 'height': h}, has_touch=True, user_agent=None if name == 'ipad' else 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
            pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(1200)
            J = lambda js, a=None: pg.evaluate("async (a) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
            await J("document.querySelector('#welGo')?.click(); await sleep(300); document.querySelector('.tour-skip')?.click(); await sleep(200); document.querySelector('.tile[data-tile=\"takes\"]')?.click(); await sleep(500);")
            await pg.set_input_files('#takeImportFile', '/home/claude/fixtures/face_clip.webm'); await pg.wait_for_timeout(5000)
            await J("document.querySelector('#takeList li')?.click(); await sleep(1200);")
            # a score on it, saved, then Studio left
            await J("document.querySelector('#studioBtn').click(); await sleep(2500);")
            img = base64.b64encode(open('/home/claude/tc/raw-002.jpg', 'rb').read()).decode()
            await J("""const S = await import('/js/studio.js'); const img = new Image(); img.src = 'data:image/jpeg;base64,' + a; await img.decode();
              const c = document.createElement('canvas'); c.width = 2080; c.height = 620; c.getContext('2d').drawImage(img, -150, -500);
              await S._addScoreFrom(c); await sleep(1500);""", img)
            await J("document.querySelector('#stBack').click(); await sleep(1500);")
            st = await J("return { studio: !document.querySelector('#studio').hidden, panel: !document.querySelector('#panel-takes').hidden, player: !document.querySelector('#player').hidden };")
            check(not st['studio'] and st['panel'] and st['player'], f'{name}: Back from Studio comes back to the same recording {st}')
            # open again, slowed down: every few ms, is the main screen showing?
            seen = await J("""const sb = createImageBitmap; window.createImageBitmap = async (...x) => { await sleep(700); return sb(...x); };
              const home = []; let t0 = performance.now(); const iv = setInterval(() => { const s = !document.querySelector('#studio').hidden, pn = !document.querySelector('#panel-takes').hidden; if (!s && !pn) home.push(Math.round(performance.now() - t0)); }, 16);
              document.querySelector('#studioBtn').click(); await sleep(3500); clearInterval(iv); window.createImageBitmap = sb;
              return { home: home.length, studio: !document.querySelector('#studio').hidden, panel: !document.querySelector('#panel-takes').hidden, busy: !document.querySelector('#stBusy').hidden, strips: (await import('/js/studio.js'))._studio.strips.size };""")
            check(seen['home'] == 0 and seen['studio'] and not seen['panel'] and not seen['busy'] and seen['strips'] == 1, f'{name}: slow opening never shows the main screen, opens with the score {seen}')
            await J("document.querySelector('#stBack').click(); await sleep(1500);")
            # a score that fails once: tried again
            r = await J("""const sb = createImageBitmap; let n = 0; window.createImageBitmap = async (...x) => { if (n++ === 0) throw new Error('memory'); return sb(...x); };
              document.querySelector('#studioBtn').click(); await sleep(3000); window.createImageBitmap = sb;
              return { studio: !document.querySelector('#studio').hidden, strips: (await import('/js/studio.js'))._studio.strips.size };""")
            check(r['studio'] and r['strips'] == 1, f'{name}: a score that fails once is drawn on the second try {r}')
            await J("document.querySelector('#stBack').click(); await sleep(1500);")
            # Studio that cannot open at all: back on the recording, with a message
            r = await J("""const S = await import('/js/studio.js'); const g = db0 = null; const orig = URL.createObjectURL; URL.createObjectURL = () => { throw new Error('no'); };
              document.querySelector('#studioBtn').click(); await sleep(1500); URL.createObjectURL = orig;
              return { studio: !document.querySelector('#studio').hidden, panel: !document.querySelector('#panel-takes').hidden, player: !document.querySelector('#player').hidden, toast: document.querySelector('#toast')?.textContent || '', opening: document.body.classList.contains('st-opening') };""")
            check(not r['studio'] and r['panel'] and r['player'] and 'could not open' in r['toast'] and not r['opening'], f'{name}: Studio that cannot open leaves you on the recording {r}')
            # and it opens normally after that
            r = await J("document.querySelector('#studioBtn').click(); await sleep(2500); return { studio: !document.querySelector('#studio').hidden, strips: (await import('/js/studio.js'))._studio.strips.size };")
            check(r['studio'] and r['strips'] == 1, f'{name}: opens again afterwards {r}')
            # double tap on the button: one Studio, still works
            await J("document.querySelector('#stBack').click(); await sleep(1500);")
            r = await J("const b = document.querySelector('#studioBtn'); b.click(); b.click(); await sleep(150); b.click(); await sleep(3000); return { studio: !document.querySelector('#studio').hidden, panel: !document.querySelector('#panel-takes').hidden, strips: (await import('/js/studio.js'))._studio.strips.size };")
            check(r['studio'] and not r['panel'] and r['strips'] == 1, f'{name}: tapping Studio several times opens it once {r}')
            # Cancel while opening: back on the recording, no message
            await J("document.querySelector('#stBack').click(); await sleep(1500);")
            r = await J("""const sb = createImageBitmap; window.createImageBitmap = async (...x) => { await sleep(1500); return sb(...x); };
              document.querySelector('#studioBtn').click(); await sleep(400); document.querySelector('#stBusyCancel').click(); await sleep(2200); window.createImageBitmap = sb;
              return { studio: !document.querySelector('#studio').hidden, panel: !document.querySelector('#panel-takes').hidden };""")
            check(not r['studio'] and r['panel'], f'{name}: Cancel while opening stays on the recording {r}')
            await pg.screenshot(path=f'/home/claude/shots/sto_{name}.png')
            check(not errs, f'{name}: no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print(f'{len(fails)} fails')
    sys.exit(1 if fails else 0)
asyncio.run(main())
