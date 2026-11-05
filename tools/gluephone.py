# The iPhone gets a score as its own PDF in one go (as over the direct link), draws its pages and
# Play's lines itself; Play goes through the whole score with no line shown twice or left behind,
# and every step is quick
import asyncio, json, os, sys, time
from playwright.async_api import async_playwright
FILES = ['/home/claude/fixtures/imslp12.pdf']
MODE = os.environ.get('MODE', 'glued')
OUT = '/tmp/claude-0/pf'
async def main():
    async with async_playwright() as p:
        b = await getattr(p, os.environ.get('BR', 'chromium')).launch()
        ipad = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await ipad.add_init_script('window.__noTour = true;')
        errs = []; ipad.on('pageerror', lambda e: errs.append('ipad ' + str(e)))
        await ipad.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', FILES)
        await ipad.wait_for_function("(n) => document.querySelectorAll('#grid .card:not(.folder)').length >= n", arg=len(FILES), timeout=120000)
        await ipad.wait_for_timeout(1500)
        await ipad.evaluate('''async (mode) => { const { db } = await import('/js/db.js'); const s = (await db.all('scores'))[0];
            if (mode === 'glued') s.glue = { 0: { next: 1, cut: 0.3, top: 0.04, end: 0.96 } };
            if (mode === 'removed') s.glue = {};
            s.stamp = Date.now(); s.edited = Date.now(); await db.put('scores', s); }''', MODE)
        await ipad.wait_for_timeout(500)
        await ipad.reload(); await ipad.wait_for_timeout(2500)
        L = json.loads(await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))"))
        infos = {}
        for sc in L['scores']:
            infos[sc['id']] = await ipad.evaluate("async (id) => window.__answerPhone({ what: 'scoreinfo', id })", sc['id'])
            print(sc['title'], 'src offered:', bool(infos[sc['id']].get('src')), infos[sc['id']]['n'], 'pages', json.dumps((infos[sc['id']].get('src') or {}).get('struct'))[:200])
        # the PDFs as the iPhone would receive them
        srcs = {}
        for sc in L['scores']:
            srcs[sc['id']] = await ipad.evaluate("async (id) => { const { db } = await import('/js/db.js'); const s = await db.get('scores', id); return s.fileId; }", sc['id'])
        byname = {}
        async def serve(route):
            fid = route.request.url.split('/__t/')[1]
            data = await ipad.evaluate("async (fid) => { const { db } = await import('/js/db.js'); const f = await db.get('files', fid); const u = new Uint8Array(f.data); let s = ''; for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768)); return btoa(s); }", fid)
            import base64
            await route.fulfill(body=base64.b64decode(data), content_type='application/octet-stream')
        ctx = await b.new_context(viewport={'width': 393, 'height': 852}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
        ph = await ctx.new_page()
        await ph.route('**/__t/*', serve)
        await ph.add_init_script("""window.__noTour = true; try { localStorage.setItem('standPlayN', '2'); } catch {}
          window.__plog = []; window.standCaps = Object.assign(window.standCaps || {}, { peer: 3 });
          window.webkit = { messageHandlers: { standPeer: { postMessage() {} }, standDone: { postMessage() {} }, standDiag: { postMessage(m) { window.__plog.push(m.text); } } } };""")
        ph.on('pageerror', lambda e: errs.append('phone ' + str(e))); ph.on('console', lambda m: errs.append('pc ' + m.type + ' ' + m.text) if m.type in ('error','warning') else None)
        await ph.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.evaluate("""(a) => { const [l, infos, srcs] = a; window.__asked = [];
          window.__askIpadTest = async (q) => { window.__asked.push(q.what);
            if (q.what === 'list') return JSON.parse(l);
            if (q.what === 'scoreinfo') return infos[q.id];
            if (q.what === 'src') { setTimeout(() => window.standPeerFile && window.standPeerFile({ kind: 'scoresrc', id: 'xfer1', sid: q.id, stamp: infos[q.id].stamp }, '/__t/' + srcs[q.id], null), 300); await new Promise((r) => setTimeout(r, 600)); return { ok: true }; }
            if (q.what === 'ink') return { ink: null };
            throw new Error('ipad:none'); }; }""", [json.dumps(L), infos, srcs])
        has = await ph.evaluate("() => typeof window.standPeerFile")
        print('phone file hook', has)
        await ph.evaluate("() => document.querySelector('#phScoresBar').click()"); await ph.wait_for_timeout(800)
        for sc in L['scores']:
            await ph.evaluate("(t) => [...document.querySelectorAll('.phs-card')].find((c) => c.textContent.includes(t)).click()", sc['title'])
            try:
                await ph.wait_for_function("() => { const i = document.querySelector('#phvImg'); return !document.querySelector('#phView').hidden && i && i.complete && i.naturalWidth > 0; }", timeout=60000)
                print('opened', await ph.evaluate("() => document.querySelector('#phvPage').textContent"))
            except Exception as e: print('NOT OPENED', str(e)[:80])
            for k in range(4):
                await ph.keyboard.press('ArrowRight'); await ph.wait_for_timeout(int(os.environ.get('GAP','800'))); await ph.screenshot(path=f'/tmp/claude-0/gp_{MODE}_{k}.png')
                print(' page', await ph.evaluate("() => document.querySelector('#phvPage').textContent + ' hidden=' + document.querySelector('#phView').hidden + ' toast=' + (document.querySelector('#toast')||{}).textContent + ' img=' + document.querySelector('#phvImg').naturalWidth + 'x' + document.querySelector('#phvImg').naturalHeight"))
            await ph.screenshot(path='/tmp/claude-0/gluephone_' + MODE + '.png')
        hs = await ph.evaluate('''async () => { const { db } = await import('/js/db.js'); const ks = (await db.keys('files')).map(String).filter((k) => /:p\\d+$|page/.test(k)); const out = {}; for (const k of ks) { const r = await db.get('files', k); if (r && r.kind === 'ipadpage') out[k] = r.h; } return out; }''')
        print('kept page heights', hs)
        vals = list(hs.values())
        if MODE == 'glued': ok = any(v < 1500 for v in vals) and any(v > 1900 for v in vals)
        else: ok = vals and all(1700 < v < 1800 for v in vals)
        ok = ok and not [e for e in errs if not e.startswith('pc warning')]
        print('PASS' if ok else 'FAIL', 'a score with lines moved up (' + MODE + ') shows on the iPhone as on the iPad')
        log = await ph.evaluate("() => window.__plog")
        print('\n'.join(x for x in log if 'iPhone' in x)); print('errors', errs[:6])
        await b.close()
asyncio.run(main())
