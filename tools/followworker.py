# The follower's page reading in its own thread gives the same notes as reading here, and the
# second opening reads nothing (kept)
import asyncio, os, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        pg = await (await b.new_context(viewport={'width': 1180, 'height': 820}, permissions=['microphone'])).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type in ('error', 'warning') and 'ERR_' not in m.text else None)
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("async () => { document.querySelector('#grid .card:not(.folder)').click(); await new Promise(r => setTimeout(r, 2500)); const on = document.querySelector('#followOn'); on.checked = true; on.dispatchEvent(new Event('change')); await new Promise(r => setTimeout(r, 6000)); }")
        r = await pg.evaluate("""async () => { const F = window.__follower; const R = await import('/js/follow-read.js');
          const c = document.createElement('canvas'); await F.render(0, c, 1600, 2263);
          let t0 = performance.now(); const here = await R.readPage(c); const tHere = performance.now() - t0;
          t0 = performance.now(); let ticks = 0; const iv = setInterval(() => ticks++, 10);
          const { db } = await import('/js/db.js'); for (const k of (await db.keys('files')).map(String)) if (k.startsWith('follow:')) await db.del('files', k); F.cache.clear(); t0 = performance.now(); const there = await F.notesOf(0); clearInterval(iv); const tThere = performance.now() - t0;
          return { here: here.seq.length, there: there.seq.length, same: JSON.stringify(here.seq.map(e => e.pcs)) === JSON.stringify(there.seq.map(e => e.pcs)), at: [here.at, there.at], tHere: Math.round(tHere), tThere: Math.round(tThere), mainTicksWhileReading: ticks, expected: Math.round(tThere / 10) }; }""")
        print(json.dumps(r))
        r2 = await pg.evaluate("""async () => { const F = window.__follower; F.cache.clear(); const t0 = performance.now(); const x = await F.notesOf(0); const { db } = await import('/js/db.js'); const ks = (await db.keys('files')).map(String).filter(k => k.startsWith('follow:'));
          return { again_ms: Math.round(performance.now() - t0), n: x.seq.length, kept: ks }; }""")
        print(json.dumps(r2)); print('errors', errs[:5]); await b.close()
asyncio.run(main())
