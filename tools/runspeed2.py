# Turning inside a set's part, and through a practice session's passages (several in one score, some
# in another): how long until the new page is drawn, with the CPU slowed 4x like an older iPad
import asyncio, time, os, json
from playwright.async_api import async_playwright
F = '/home/claude/fixtures/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;')
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(700)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await pg.set_input_files('#importInput', [F + 'imslp12.pdf', F + 'scan10.pdf', F + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 3", timeout=90000)
        await pg.wait_for_timeout(5000)
        ids = await J("const { db } = await import('/js/db.js'); return (await db.all('scores')).map(s => s.id)")
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        drawn = "document.querySelector('#stage canvas.art') && [...document.querySelectorAll('#stage canvas.art')].every(c=>c.width>10)"
        async def timed(js, cond, label):
            t0 = time.time(); await J(js)
            await pg.wait_for_function(cond + ' && ' + drawn, timeout=60000)
            print(label, int((time.time() - t0) * 1000), 'ms', await J("return document.querySelector('#pageLabel').textContent"), flush=True)
        # a set of one long part: turning inside it
        await J(f"window.__run.startRun('set', 'T', {json.dumps([{'sid': ids[0], 'a': 1, 'b': 12}, {'sid': ids[1], 'a': 1, 'b': 4}])}); await sleep(300);")
        await pg.wait_for_function(drawn, timeout=60000)
        for k in range(3):
            await pg.wait_for_timeout(1500)
            want = 3 + 2 * k
            await timed("window.standTurn(1);", f"document.querySelector('#pageLabel').textContent.startsWith('{want}')", f'set, inside a part, turn {k+1}:')
        await J("window.__run.endRun(); await sleep(300);")
        # a practice session: passages on single pages (orig), several in one score, then another score
        items = [{'sid': ids[0], 'orig': 2, 'name': 'A'}, {'sid': ids[0], 'orig': 5, 'name': 'B'}, {'sid': ids[1], 'orig': 3, 'name': 'C'}, {'sid': ids[0], 'orig': 9, 'name': 'D'}]
        await J(f"window.__run.startRun('study', 'S', {json.dumps(items)}); await sleep(300);")
        await pg.wait_for_function(drawn, timeout=60000)
        for k in range(1, 4):
            await pg.wait_for_timeout(1500)
            want = items[k]['orig'] + 1
            await timed(f"window.__run.runGo({k});", f"window.__run.RUN.idx === {k} && !window.__run.RUN.busy && document.querySelector('#pageLabel').textContent.startsWith('{want}')", f'session, to passage {k+1} ({"same" if items[k]["sid"] == items[k-1]["sid"] else "other"} score):')
        print(errs[:3]); await b.close()
asyncio.run(main())
