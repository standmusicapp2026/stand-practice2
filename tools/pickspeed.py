# Choosing the music for a video (Add score): turning through the pages to find the one wanted. Each
# turn: how long until the page shows, how long until its lines can be tapped, and the longest time
# the screen was frozen (main thread busy). On an older iPad's speed too (CPU slowed 4x).
#   FILE=<pdf in fixtures> (default imslp12.pdf), SLOW=4
import asyncio, os, json
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await getattr(p, os.environ.get('BR', 'chromium')).launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        await pg.add_init_script("""window.__long = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push([Math.round(e.startTime), Math.round(e.duration)]); }).observe({ entryTypes: ['longtask'] }); } catch {}""")
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + os.environ.get('FILE', 'imslp12.pdf')])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
        await pg.wait_for_timeout(3000)
        slow = float(os.environ.get('SLOW', '1'))
        if slow > 1:
            cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': slow})
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("const { db } = await import('/js/db.js'); const s = (await db.all('scores'))[0]; const P = await import('/js/picker.js'); P.pickRegion({ scoreId: s.id, page: 0 }, null, { title: 'test' }); for (let i = 0; i < 100 && document.querySelector('#pkStage').hidden; i++) await sleep(100);")
        await pg.wait_for_timeout(1500)
        pages = await J("return document.querySelector('#pkPageNo').textContent")
        print('picker open:', pages, flush=True)
        res = []
        for k in range(int(os.environ.get('TURNS', '8'))):
            r = await J("""window.__long = []; const t0 = performance.now(); const label = document.querySelector('#pkPageNo').textContent;
              const c0 = document.querySelector('#pkCanvas'); const sig0 = c0.width + 'x' + c0.height + ':' + c0.getContext('2d').getImageData(c0.width >> 1, c0.height >> 2, 1, 1).data.join(',');
              document.querySelector('#pkNext').click();
              let shown = null, lines = null;
              for (let i = 0; i < 600; i++) {
                await sleep(25);
                const c = document.querySelector('#pkCanvas');
                if (shown === null && document.querySelector('#pkPageNo').textContent !== label && c.width > 10) { const sig = c.width + 'x' + c.height + ':' + c.getContext('2d').getImageData(c.width >> 1, c.height >> 2, 1, 1).data.join(','); if (sig !== sig0) shown = performance.now() - t0; }
                if (lines === null && document.querySelector('#pkFinding').hidden && document.querySelector('#pkPageNo').textContent !== label) lines = performance.now() - t0;
                if (shown !== null && lines !== null) break;
              }
              const lt = window.__long.filter((x) => x[0] >= t0 - 5).map((x) => x[1]);
              const P = await import('/js/picker.js'); return [document.querySelector('#pkPageNo').textContent + ' (' + ((P._pk.lines || []).length) + ' lines, ' + (P._pk.lines || []).map((L) => L.y0.toFixed(3)).slice(0, 3).join('/') + ')', Math.round(shown ?? -1), Math.round(lines ?? -1), lt.length ? Math.max(...lt) : 0, lt.reduce((a, v) => a + v, 0)];""")
            res.append(r); print(f'{r[0]:48s} shown {r[1]:5d} ms   lines ready {r[2]:5d} ms   longest freeze {r[3]:5d} ms (frozen {r[4]} ms in all)', flush=True)
            await pg.wait_for_timeout(int(os.environ.get('GAP', '300')))
        # the same score again (the lines read before are kept)
        await J("document.querySelector('#pkCancel').click(); await sleep(300); document.querySelector('#pkCancel').click(); await sleep(500);")
        await J("const { db } = await import('/js/db.js'); const s = (await db.all('scores'))[0]; const P = await import('/js/picker.js'); P.pickRegion({ scoreId: s.id, page: 0 }, null, { title: 'test' }); for (let i = 0; i < 100 && document.querySelector('#pkStage').hidden; i++) await sleep(100);")
        await pg.wait_for_timeout(800)
        again = []
        for k in range(4):
            r = await J("""const t0 = performance.now(); const label = document.querySelector('#pkPageNo').textContent; document.querySelector('#pkNext').click();
              for (let i = 0; i < 400; i++) { await sleep(25); if (document.querySelector('#pkPageNo').textContent !== label && document.querySelector('#pkFinding').hidden) break; }
              const P = await import('/js/picker.js'); return [document.querySelector('#pkPageNo').textContent + ' (' + ((P._pk.lines || []).length) + ' lines)', Math.round(performance.now() - t0), 0];""")
            again.append(r); print('again:', r[0], 'lines ready', r[1], 'ms', flush=True)
        print('errors', errs[:3])
        print('SUMMARY shown avg', round(sum(r[1] for r in res) / len(res)), 'ms; lines avg', round(sum(r[2] for r in res) / len(res)), 'ms; worst freeze', max(r[3] for r in res), 'ms')
        await b.close()
asyncio.run(main())
