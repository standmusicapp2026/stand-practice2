# The backup as one folder kept up to date: only what changed is written; leaving the app brings it
# up to date by itself; everything comes back from the folder (scores, folders, markings)
import asyncio, os, json
from playwright.async_api import async_playwright
MOCK = r"""
(() => {
  const files = window.__docs = window.__docs || {};
  window.__writes = [];
  window.standCaps = { native: true, files: 3 };
  const open = {};
  window.webkit = { messageHandlers: { standSave: { postMessage: (m) => {
    if (m.op === 'begin') open[m.id] = { path: (m.folder ? m.folder + '/' : '') + m.name, parts: [] };
    else if (m.op === 'chunk') { open[m.id].parts.push(m.data); setTimeout(() => window.standSavedChunk && window.standSavedChunk({ id: m.id }), 1); }
    else if (m.op === 'end') { const o = open[m.id]; delete open[m.id]; const bin = o.parts.map((b) => atob(b)).join(''); const u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); files[o.path] = new Blob([u8]); window.__writes.push(o.path); setTimeout(() => window.standSaved({ id: m.id, ok: true, path: o.path }), 1); }
    else if (m.op === 'remove') delete files[m.path];
    else if (m.op === 'purge') window.__purged = (window.__purged || 0) + 1;
  } }, standBusy: { postMessage: () => {} } } };
  const f0 = window.fetch.bind(window);
  window.fetch = (u, o) => { const s = String(u); if (s.startsWith('/__docs/')) { const p = 'Backup/' + s.slice(8).split('/').map(decodeURIComponent).join('/'); const b = files[p]; return Promise.resolve(b ? new Response(b) : new Response('', { status: 404 })); } return f0(u, o); };
})();
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(MOCK)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT','8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf', '/home/claude/fixtures/scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=90000)
        await pg.wait_for_timeout(3000)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        async def backup():
            await J("window.__writes = []; document.querySelector('[data-panel=backup]')?.click(); await sleep(300); document.querySelector('#bkMake').click(); for (let i = 0; i < 200 && document.querySelector('#bkMake').disabled; i++) await sleep(100); await sleep(500);")
            return await J("return window.__writes.slice()")
        w1 = await backup(); print('first backup wrote', len(w1), 'files:', sorted(w1)[:6])
        w2 = await backup(); print('nothing changed, wrote', w2)
        # a marking on a score, and a score moved into a new folder
        await J("const s = (await db.all('scores'))[0]; await db.put('ink', { key: s.id + ':0', items: [{ t: 'pen', c: '#000', s: 2, p: [[0.1,0.1,0.5],[0.2,0.2,0.5]] }] }); const f = { id: 'fold1', name: 'Etudes', created: Date.now() }; await db.put('kv', { k: 'folders', v: [f] }); s.folder = 'fold1'; await db.put('scores', s);")
        w3 = await backup(); print('a marking + a move, wrote', w3)
        # leaving the app: brought up to date by itself
        await J("const s = (await db.all('scores'))[1]; s.title = 'Renamed'; await db.put('scores', s); window.__writes = []; Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); for (let i = 0; i < 100 && !window.__writes.includes('Backup/Stand library.json'); i++) await sleep(100); Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });")
        print('on leaving the app, wrote', await J("return window.__writes"))
        print('old zips cleared', await J("return window.__purged || 0"))
        # everything wiped, then brought back from the folder
        await J("for (const st of ['scores', 'files', 'ink']) for (const x of await db.all(st)) await db.del(st, x.id || x.key);")
        print('wiped:', await J("return (await db.all('scores')).length"))
        try: await J("document.querySelector('#bkFromFolder').hidden = false; document.querySelector('#bkFromFolder').click(); await sleep(8000);")
        except Exception as e: print('(Stand started again after restoring)')
        await pg.wait_for_timeout(4000)
        print('restored:', await J("const s = await db.all('scores'); const f = await db.all('files'); const ink = await db.all('ink'); return { scores: s.map(x => [x.title, x.folder || '-']), files: f.length, ink: ink.filter(x => x.items && x.items.length).length }"))
        print(errs[:3]); await b.close()
asyncio.run(main())
