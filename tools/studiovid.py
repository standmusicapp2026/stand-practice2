# (studiovid) The Studio with two lines: the players' video imported into Recordings, the first
# clarinet's 4M30 (bars 1-19) as the score, the second clarinet's as a second line under it, each
# following its own player ("Follow my playing"), just the lines over the video. The video is then
# drawn frame by frame by the Studio itself and put together with the video's own sound.
import asyncio, base64, json, os, subprocess, sys, time
from playwright.async_api import async_playwright
D = '/home/claude/dragon'
PDF = [f'{D}/out/How to Train Your Dragon 2 - Clarinet 1.pdf', f'{D}/out/How to Train Your Dragon 2 - Clarinet 2.pdf']
PAGE = [48, 46]       # 4M30's first page in each part
LINES = (0, 5)        # its lines 1-6: bars 1-19
READ = [f'{D}/app1.json', f'{D}/app2.json']
LOOK = os.environ.get('LOOK', 'lines')
OUT = f'{D}/studio'; os.makedirs(OUT, exist_ok=True)
FPS = int(os.environ.get('FPS', '30'))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, device_scale_factor=1)
        pg = await ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__noTour = true; window.__noTempo = true;")
        await pg.goto('http://localhost:8765/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        # the video into Recordings, as "Import a video" does
        await pg.set_input_files('#takeImportFile', f'{D}/4M30 clarinetes.webm')
        await pg.wait_for_function("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return t.length > 0 && t[0].pcm; }", timeout=120000, polling=1000)
        take = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); const t = await db.all('takes'); return { id: t[0].id, dur: t[0].dur, name: t[0].name }; }")
        print('take', take)
        await pg.evaluate("async (id) => { const S = await import('/js/studio.js'); await S.openStudio(id); }", take['id'])
        await pg.wait_for_timeout(2500)
        # the two parts: the lines of 4M30 drawn around (the picker's region), first part then the second line
        for x in (0, 1):
            pages = json.load(open(READ[x]))
            ls = sorted(pages[PAGE[x]]['lines'], key=lambda L: L['y0'])
            y0, y1 = ls[LINES[0]]['y0'], ls[LINES[1]]['y1']
            data = base64.b64encode(open(PDF[x], 'rb').read()).decode()
            info = await pg.evaluate("""async ([b64, page, y0, y1, second]) => {
              const { openDocument } = await import('/js/score.js'); const bin = atob(b64), u = new Uint8Array(bin.length); for (let k = 0; k < bin.length; k++) u[k] = bin.charCodeAt(k);
              const doc = await openDocument({ kind: 'pdf', data: u.buffer }); const [pw, ph] = doc.sizes[page];
              const W = 2000, H = Math.round(W * ph / pw); const c = document.createElement('canvas'); await doc.render(page, c, W, H);
              const r = document.createElement('canvas'); r.width = W; r.height = Math.round((y1 - y0) * H); r.getContext('2d').drawImage(c, 0, Math.round(y0 * H), W, r.height, 0, 0, W, r.height);
              const S = await import('/js/studio.js'); const o = await S._addScoreFrom(r, { second });
              o.title = second ? 'Clarinet 2 · 4M30' : 'Clarinet 1 · 4M30';
              return { bars: o.layout.bars.length, id: o.id }; }""", [data, PAGE[x], y0, y1, x == 1])
            print('line', x + 1, info, flush=True)
        # the look chosen for both lines (one system): just the lines, white ink with its soft shade
        await pg.evaluate("""async (look) => { const S = await import('/js/studio.js'); const ls = S._studio.P.overlays.filter((o) => o.kind === 'score');
          for (const o of ls) { o.look = look; o.ink = '#ffffff'; o.mode = 'scroll'; o.band = true; o.perView = 3; o.size = 0.96; o.highlight = true; }
          ls[0].pos = { x: 0.5, y: 0.66 }; S._frame(); }""", LOOK)
        # each line follows its own player
        for x in (0, 1):
            t0 = time.time()
            r = await pg.evaluate("""async (x) => { const S = await import('/js/studio.js'); const o = S._studio.P.overlays.filter((q) => q.kind === 'score')[x];
              await S._autoSync(o); return { synced: o.synced, info: o.syncInfo ? { good: o.syncInfo.good, how: o.syncInfo.how } : null, times: o.times.map((t) => +t.toFixed(2)) }; }""", x)
            print('follow line', x + 1, round(time.time() - t0), 's', r, flush=True)
        # (put the two lines one under the other again, now that they have their size)
        await pg.evaluate("""async () => { const S = await import('/js/studio.js'); S._frame(); }""")
        await pg.screenshot(path=f'{OUT}/studio.png')
        # the video, frame by frame, as the Studio draws it for export
        dur = take['dur']; n = int(dur * FPS)
        os.makedirs(f'{OUT}/f', exist_ok=True)
        for i in range(n):
            t = i / FPS
            jpg = await pg.evaluate("""async (t) => { const S = await import('/js/studio.js'); const m = S._studio.media;
              if (Math.abs(m.currentTime - t) > 0.001) { await new Promise((res) => { const done = () => { m.removeEventListener('seeked', done); res(); }; m.addEventListener('seeked', done); m.currentTime = t; setTimeout(done, 1500); }); }
              const c = window.__stc || (window.__stc = document.createElement('canvas')); S._drawAt(c, t); return c.toDataURL('image/jpeg', 0.9).split(',')[1]; }""", t)
            open(f'{OUT}/f/{i:05d}.jpg', 'wb').write(base64.b64decode(jpg))
            if i % 150 == 0: print('frame', i, '/', n, flush=True)
        print('errors', errs[:5])
        await b.close()
asyncio.run(main())
