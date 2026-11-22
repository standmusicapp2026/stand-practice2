# (dragonpick) As the user does it: the Studio, a video, Sync > the score, the Dragon part, page 5
# (1M0, slurs over high tremolo notes, a tempo mark), all its lines chosen. The long line keeps every
# note: each piece of ink of the page that touches a chosen staff is in the strip, whole.
import asyncio, base64, os, sys
from playwright.async_api import async_playwright
SP = '/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad'
PDF = '/home/claude/dragon/out/How to Train Your Dragon 2 - Clarinet 1.pdf'
PAGES = [int(x) for x in os.environ.get('PAGES', '4').split(',')]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', [PDF])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
        await pg.set_input_files('#takeImportFile', '/home/claude/dragon/clar40.mp4')
        for _ in range(90):
            if await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0; }"): break
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(3000)
        tid = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return (await db.all('takes'))[0].id; }")
        await pg.evaluate("async (id) => { const S = await import('/js/studio.js'); await S.openStudio(id); }", tid)
        await pg.wait_for_timeout(1500)
        J = lambda js, a=None: pg.evaluate("async (A) => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }", a)
        allok = True
        for page in PAGES:
            await J("const S = await import('/js/studio.js'); S._studio.P.overlays = S._studio.P.overlays.filter((x) => x.kind !== 'score'); document.querySelector('#stSyncBtn').click(); await sleep(900); [...document.querySelectorAll('#pkLib .card')].find(c => /Dragon/i.test(c.textContent)).click(); await sleep(1500);")
            for _ in range(page):
                await J("document.querySelector('#pkNext').click(); await sleep(250);")
            await pg.wait_for_timeout(800); await pg.wait_for_function("document.querySelector('#pkFinding').hidden", timeout=60000); await pg.wait_for_timeout(500)
            await J("document.querySelector('#pkAll').click(); await sleep(300); document.querySelector('#pkDone').click();")
            await pg.wait_for_function("(async () => true)() && document.querySelector('#busy') ? document.querySelector('#busy').hidden !== false : true", timeout=90000)
            for _ in range(60):
                n = await J("const S = await import('/js/studio.js'); const o = S._studio.P.overlays.find((x) => x.kind === 'score'); return o && S._studio.strips.get(o.id) ? 1 : 0;")
                if n: break
                await pg.wait_for_timeout(500)
            r = await J("""const S = await import('/js/studio.js'); const o = S._studio.P.overlays.find((x) => x.kind === 'score'); const st = S._studio.strips.get(o.id).canvas, L = o.layout;
              const bmp = await createImageBitmap(o.img); const src = document.createElement('canvas'); src.width = bmp.width; src.height = bmp.height; src.getContext('2d').drawImage(bmp, 0, 0);
              const small = (c, mw) => { const s = document.createElement('canvas'); s.width = Math.min(c.width, mw); s.height = Math.round(c.height * s.width / c.width); s.getContext('2d').drawImage(c, 0, 0, s.width, s.height); return s.toDataURL('image/png').split(',')[1]; };
              return { png: small(st, 7000), src: small(src, 2400), bars: L.bars.length, segs: L.segs.length, notes: L.notes.length, w: st.width, h: st.height };""")
            open(f'{SP}/dpick-{page}.png', 'wb').write(base64.b64decode(r.pop('png'))); open(f'{SP}/dpick-src-{page}.png', 'wb').write(base64.b64decode(r.pop('src')))
            print(page, r, flush=True)
        print('DONE', errs[:3])
        await b.close()
asyncio.run(main())
