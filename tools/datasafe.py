# Data safety:
# 1. markings that could not be read (the database failing for a while) are never written over: what
#    is written meanwhile is added to them
# 2. a composition edited and then the app sent to the background at once keeps the edit
# 3. practice time counts up to the moment Stand goes to the background
# 4. the folder backup with a recording: written once, then not again when nothing changed; comes back
import asyncio, os, json
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
MIRROR = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mirrorbk.py')).read().split('MOCK = r"""')[1].split('"""')[0]
FAILINK = r"""
(() => {
  // the 'ink' store cannot be read until window.__inkOk (as when iOS drops the database connection)
  const g0 = IDBObjectStore.prototype.get;
  IDBObjectStore.prototype.get = function (k) { if (this.name === 'ink' && !window.__inkOk && window.__inkFail) throw new DOMException('Connection to Indexed Database server lost', 'UnknownError'); return g0.call(this, k); };
})();
"""
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(FAILINK); await pg.add_init_script(MIRROR)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        hide = "Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pagehide'));"
        show = "Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange'));"
        # ---- 1. markings that cannot be read
        sid = await J("const s = (await db.all('scores'))[0]; await db.put('ink', { key: s.id + ':0', items: [{ t: 'pen', c: '#123', s: 2, p: [[0.1,0.1,0.5],[0.3,0.3,0.5]], old: 1 }] }); return s.id;")
        await J("window.__inkFail = true; document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500);")
        await J("document.querySelector('#inkBtn').click(); await sleep(400);")
        await J("""const t = document.querySelector('#stage'); const pgEl = document.querySelector('#stage .pg'); const r = pgEl.getBoundingClientRect(); const x = r.left + r.width * 0.5, y = r.top + r.height * 0.4;
          const ev = (type, dx) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 7, pointerType: 'pen', isPrimary: true, clientX: x + dx, clientY: y, pressure: 0.5, buttons: type === 'pointerup' ? 0 : 1 }));
          ev('pointerdown', 0); for (let k = 1; k < 10; k++) { ev('pointermove', k * 8); await sleep(16); } ev('pointerup', 80); await sleep(2500);""")
        mid = await J(f"window.__inkOk = true; const r = await db.get('ink', '{sid}:0'); return r ? r.items.length : -1;")
        await J("await sleep(6500);")
        after = await J(f"const r = await db.get('ink', '{sid}:0'); return r ? [r.items.length, r.items.some(x => x.old)] : null;")
        print('ink while unreadable', mid, 'after', after)
        ok(mid == 1 and after == [2, True], 'markings that could not be read are kept, the new one added to them')
        await J("document.querySelector('#backBtn').click(); await sleep(1000);")
        # ---- 3. practice time up to leaving
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2000);")
        t0 = await J(f"const s = await db.get('scores', '{sid}'); return s.seconds || 0;")
        await J("await sleep(9000);" + hide + "await sleep(800);")
        t1 = await J(f"const s = await db.get('scores', '{sid}'); return s.seconds || 0;")
        await J(show + "await sleep(300); document.querySelector('#backBtn').click(); await sleep(1000);")
        print('practice seconds', t0, t1)
        ok(t1 - t0 >= 8, 'practice time counts up to the moment Stand leaves')
        # ---- 2. a composition edited, then the app leaves at once
        await J("const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'Quick', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(1200);")
        await J("const M = await import('/js/compose/model.js'); const C = window.__compose; const st = M.allStaves(C.score)[0]; window.__cid = C.id; C.score.title = 'Edited just now'; C.saveT = setTimeout(() => {}, 100000);" + hide + "await sleep(800);")
        comp = await J("const s = await db.get('scores', window.__cid); return s.title;")
        await J(show)
        ok(comp == 'Edited just now', f'a composition is written as Stand leaves ({comp})')
        await J("document.querySelector('#cpBack, #composeBack, [data-close-compose]')?.click(); await sleep(800);")
        # ---- 4. backup with a recording
        await J("""const id = 'rt1'; const n = 48000 * 3; const f = new Float32Array(n); for (let i = 0; i < n; i++) f[i] = Math.sin(i / 20) * 0.5;
          await db.put('files', { id: 'audio:' + id, data: f }); await db.put('takes', { id, kind: 'audio', name: 'Test take', created: Date.now(), sr: 48000, dur: 3, scoreId: null, page: 0 });""")
        async def backup():
            await J("window.__writes = []; document.querySelector('[data-panel=app]').click(); await sleep(300); document.querySelector('[data-panel=backup]')?.click(); await sleep(400); document.querySelector('#bkMake').click(); for (let i = 0; i < 300 && document.querySelector('#bkMake').disabled; i++) await sleep(100); await sleep(600);")
            return await J("return window.__writes.slice()")
        w1 = await backup(); w2 = await backup()
        wav = [x for x in w1 if x.endswith('.wav')]
        print('backup 1', len(w1), wav, 'backup 2', w2)
        same = await J("const { mirrorSig, mirrorWav, mirrorWavSig } = await import('/js/backup.js'); const r = await db.get('files', 'audio:rt1'); return (await mirrorSig(mirrorWav(r.data, 48000))) === mirrorWavSig(r.data, 48000);")
        back = await J("const b = window.__docs['Backup/' + Object.keys(window.__docs).map(k => k.slice(7)).find(k => k.endsWith('.wav'))]; return b ? b.size : 0;")
        ok(len(wav) == 1 and w2 == ['Backup/Stand library.json'] or (len(wav) == 1 and all(not x.endswith('.wav') for x in w2)), 'a recording is written once to the backup, not again when unchanged')
        ok(same and back == 44 + 48000 * 3 * 2, f'the quick check of a recording matches the full one ({same}, {back})')
        print(errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'data safety')
        await b.close()
asyncio.run(main())
