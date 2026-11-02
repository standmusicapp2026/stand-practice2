# Bringing back a backup over a library in use: what was changed since the backup stays (a new
# title, a marking erased), what is only in the backup comes back (a score deleted since)
import asyncio, os
from playwright.async_api import async_playwright
MOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mirrorbk.py')).read().split('MOCK = r"""')[1].split('"""')[0]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(MOCK)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf', '/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
        await pg.wait_for_timeout(2000)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        ids = await J("const all = await db.all('scores'); const a = all[0]; await db.put('ink', { key: a.id + ':0', items: [{ t: 'pen', c: '#000', s: 2, p: [[0.1,0.1,0.5],[0.2,0.2,0.5]], id: 'k1' }, { t: 'pen', c: '#f00', s: 2, p: [[0.3,0.3,0.5],[0.4,0.4,0.5]], id: 'k2' }] }); return all.map(x => x.id);")
        await J("window.__writes = []; document.querySelector('[data-panel=backup]')?.click(); await sleep(300); document.querySelector('#bkMake').click(); for (let i = 0; i < 200 && document.querySelector('#bkMake').disabled; i++) await sleep(100); await sleep(500);")
        # since the backup: score A renamed and one marking erased; score B deleted
        await J(f"""const a = await db.get('scores', '{ids[0]}'); a.title = 'Renamed since'; a.edited = Date.now() + 1000; await db.put('scores', a);
          await db.put('ink', {{ key: '{ids[0]}:0', items: [{{ t: 'pen', c: '#000', s: 2, p: [[0.1,0.1,0.5],[0.2,0.2,0.5]], id: 'k1' }}] }});
          await db.del('scores', '{ids[1]}');""")
        await J("window.__restoring = true; const r = await (await import('/js/backup.js')).restoreMirror(async (path) => { const b = window.__docs['Backup/' + path]; return b || null; }); window.__r = r;")
        res = await J(f"""const a = await db.get('scores', '{ids[0]}'), b2 = await db.get('scores', '{ids[1]}'), ink = await db.get('ink', '{ids[0]}:0');
          return [a && a.title, !!b2, ink ? ink.items.length : -1];""")
        print('after restore', res)
        ok = res[0] == 'Renamed since' and res[1] and res[2] == 1
        print('PASS' if ok else 'FAIL', 'restore keeps what changed since and brings back what was lost'); print(errs[:3])
        await b.close()
asyncio.run(main())
