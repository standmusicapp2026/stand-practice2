# Stress: a 500-page score, a 200-page scan (100 MB), a library of 1000 scores.
# Times, memory (JS heap, DOM nodes, event listeners, canvas pixels) and errors, with limits.
import asyncio, os, time, json
from playwright.async_api import async_playwright
BIG = '/home/claude/fixtures/big/'
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--enable-precise-memory-info'])
        ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true; window.__rej = []; addEventListener("unhandledrejection", e => window.__rej.push(String(e.reason && e.reason.stack || e.reason).slice(0, 600)));')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Performance.enable')
        async def mem(tag):
            await cdp.send('HeapProfiler.collectGarbage')
            m = {x['name']: x['value'] for x in (await cdp.send('Performance.getMetrics'))['metrics']}
            px = await pg.evaluate("() => { let n = 0, c = 0; for (const x of document.querySelectorAll('canvas')) { n += x.width * x.height; c++; } return [c, Math.round(n / 1e6)]; }")
            r = {'heapMB': round(m['JSHeapUsedSize'] / 1e6), 'nodes': int(m['Nodes']), 'listeners': int(m['JSEventListeners']), 'canvases': px[0], 'canvasMpx': px[1]}
            print('  mem', tag, r, flush=True); return r
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        m0 = await mem('start')
        # ---- A: 500 pages
        t = time.time(); await pg.set_input_files('#importInput', [BIG + 'vector500.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=240000)
        ti = time.time() - t; print('import 500 pages', round(ti, 1), 's')
        ok(ti < 60, f'a 500-page PDF is added in under a minute ({ti:.1f} s)')
        t = time.time(); await J("document.querySelector('#grid .card:not(.folder)').click();")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c => c.width > 10)", timeout=60000)
        to = time.time() - t; ok(to < 6, f'it opens in {to:.1f} s')
        # turn 150 pages quickly with the keyboard (like a pedal)
        t = time.time()
        for i in range(150): await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(60)
        await pg.wait_for_timeout(1500)
        tt = time.time() - t
        m1 = await mem('after 150 turns')
        ok(m1['canvases'] - m0['canvases'] < 30 and m1['canvasMpx'] < 120, f'turning many pages keeps few canvases (+{m1["canvases"] - m0["canvases"]}, {m1["canvasMpx"]} Mpx)')
        # the Pages panel with 500 pages: pictures made only when seen
        t = time.time(); await J("document.querySelector('#score [data-panel=settings]')?.click(); await sleep(300); document.querySelector('#pagesBtn, [data-panel=\"pages\"], #pgOpen')?.click(); await sleep(1500);")
        tp = time.time() - t
        drawn = await J("return [...document.querySelectorAll('#pageGrid canvas')].filter(c => c.getContext('2d').getImageData(c.width/2|0, c.height/3|0, 1, 1).data[3] > 0).length")
        cells = await J("return document.querySelectorAll('#pageGrid .pcell').length")
        print('pages panel', round(tp, 1), 's', cells, 'cells', drawn, 'drawn')
        ok(cells == 500 and drawn < 120, f'Pages: 500 pages listed, only those in view drawn ({drawn})')
        await J("const b = document.querySelector('#panel-pages .panel-body'); for (let i = 0; i < 30; i++) { b.scrollTop += 600; await sleep(60); } await sleep(1500); document.querySelector('#panel-pages [data-close]').click(); await sleep(600);")
        m2 = await mem('after Pages scrolled and closed')
        ok(m2['canvasMpx'] - m1['canvasMpx'] < 10 and m2['canvases'] - m1['canvases'] < 20, f'the Pages panel closed lets its pictures go ({m2["canvases"]} canvases, {m2["canvasMpx"]} Mpx)')
        # writing on 20 pages, turning between
        for i in range(20):
            await J("""const t = document.querySelector('#stage'); const pgEl = document.querySelector('#stage .pg'); const r = pgEl.getBoundingClientRect(); const x = r.left + r.width * 0.4, y = r.top + r.height * 0.4;
              const ev = (type, dx) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 9, pointerType: 'pen', isPrimary: true, clientX: x + dx, clientY: y + dx / 3, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
              ev('pointerdown', 0); for (let k = 1; k < 12; k++) { ev('pointermove', k * 7); await sleep(8); } ev('pointerup', 84); await sleep(100);""")
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(150)
        await J("document.querySelector('#backBtn').click(); await sleep(2500);")
        m3 = await mem('back home after 500-page score')
        inks = await J("return (await db.keys('ink')).length")
        ok(inks >= 19, f'markings on 20 pages kept ({inks})')
        # ---- B: 200-page scan (100 MB)
        t = time.time(); await pg.set_input_files('#importInput', [BIG + 'scan200.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=300000)
        ts = time.time() - t; print('import 100 MB scan', round(ts, 1), 's')
        ok(ts < 120, f'a 100 MB scanned PDF is added ({ts:.1f} s)')
        await J("[...document.querySelectorAll('#grid .card:not(.folder)')].find(c => c.querySelector('.ttl').textContent.includes('scan')).click();")
        await pg.wait_for_function("document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c => c.width > 10)", timeout=60000)
        for i in range(60): await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(80)
        await pg.wait_for_timeout(1500)
        m4 = await mem('scan, 60 turns')
        ok(m4['canvasMpx'] < 150, f'scan: canvas memory stays low ({m4["canvasMpx"]} Mpx)')
        await J("document.querySelector('#backBtn').click(); await sleep(2500);")
        # ---- C: 1000 scores
        await J("""const all = await db.all('scores'); const s = all[0]; for (let i = 0; i < 1000; i++) await db.put('scores', { ...s, id: 'many' + i, title: 'Study ' + i + ' ' + ['Bach','Popper','Duport','Piatti','Grützmacher'][i % 5], composer: ['Bach','Popper','Duport','Piatti','Grützmacher'][i % 5], added: Date.now() - i * 1000 });""")
        t = time.time(); await pg.reload(); await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1000", timeout=60000); tl = time.time() - t
        ok(tl < 8, f'a library of 1000 scores shows in {tl:.1f} s')
        await pg.evaluate("() => { window.__lt = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: true }); }")
        await pg.wait_for_timeout(3000)
        print('long tasks after start', await pg.evaluate("() => window.__lt.slice(0, 20)"))
        t = time.time(); await pg.fill('#searchInput', 'Study 6 Popper'); await pg.wait_for_timeout(50); tq = time.time() - t
        n = await J("return document.querySelectorAll('#grid .card:not(.folder)').length")
        ok(tq < 1.0 and n >= 1, f'search in 1000 scores: {tq*1000:.0f} ms, {n} found')
        await pg.fill('#searchInput', '')
        t = time.time(); await J("document.querySelector('#sortSeg button[data-sort=title]').click(); await sleep(20);"); tsort = time.time() - t
        ok(tsort < 1.5, f'sorting 1000 scores: {tsort*1000:.0f} ms')
        m5 = await mem('library of 1000')
        ok(m5['heapMB'] < 400, f'heap with 1000 scores {m5["heapMB"]} MB')
        print('noted', await pg.evaluate('() => window.__standErrors.map(x => x.line).slice(0, 3)'))
        print('rejections', await pg.evaluate('() => window.__rej.slice(0, 3)'))
        # (pdf.js reports a drawing stopped on purpose, turning past a page, as an error of its own: not ours)
        errs = [e for e in errs if 'RenderingCancelledException' not in e]
        print('errors', errs[:5]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'stress'); await b.close()
asyncio.run(main())
