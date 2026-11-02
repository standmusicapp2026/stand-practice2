# A score open with listening and eyes on: the camera and the face model run, the follower gets a
# place on the page from the eyes, nothing breaks
import asyncio, json
from playwright.async_api import async_playwright
Y4M = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/faces/face.y4m'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-video-capture={Y4M}', '--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, permissions=['camera', 'microphone'])
        pg = await ctx.new_page()
        await pg.add_init_script('window.__noTour = true; window.__gazeCpu = ' + ('true' if 'cpu' in __import__('sys').argv else 'false') + ';')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        # settings: listening and eyes on, with a set-up for this screen (a plain mapping: the iris across and up)
        await pg.evaluate("""async () => { const { getSetting, setSetting } = await import('/js/db.js'); const S = (await getSetting('settings', {})) || {};
          const wx = [590, 2000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], wy = [410, 0, 1500, 0, 0, 0, 0, 0, 0, 0, 0, 0];
          S.followTurn = true; S.followEyes = true; S.eyesCal = { land: { wx, wy, err: 70, w: 1180, h: 820 } }; await setSetting('settings', S); }""")
        await pg.reload(); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); }")
        await pg.set_input_files('#importInput', '/home/claude/fixtures/vector8.pdf'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(3000)
        for i in range(12):
            await pg.wait_for_timeout(1500)
            r = await pg.evaluate("() => { const f = window.__follower; return f ? { on: f.on, gaze: f.gaze ? f.gaze() : 'none', trust: f.trust } : null; }")
            if r and r['gaze'] not in (None, 'none'): break
        print(json.dumps(r)); print(await pg.evaluate("() => { const g = window.__eyes.gaze; return g ? { on: g.on, err: g.err, del: g.delegate, worker: !!g.worker, avg: g.avgMs, last: g.last && { face: g.last.face, q: g.last.quality, x: g.last.x } } : null; }"))
        print(errs[:5]); await b.close()
asyncio.run(main())
