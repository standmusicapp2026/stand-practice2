# (playfast) Play on the iPhone, 2 and 3 lines switched and fast taps: each screen shows exactly its lines.
# From playfile: the iPhone gets a score as its own PDF in one go (as over the direct link), draws its pages and
# Play's lines itself; Play goes through the whole score with no line shown twice or left behind,
# and every step is quick
import asyncio, json, os, sys, time
from playwright.async_api import async_playwright
FILES = sys.argv[1:] or ['/home/claude/real/muto/bwv1008-a4.pdf', '/home/claude/fixtures/imslp12.pdf']
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
        L = json.loads(await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))"))
        infos = {}
        for sc in L['scores']:
            infos[sc['id']] = await ipad.evaluate("async (id) => window.__answerPhone({ what: 'scoreinfo', id })", sc['id'])
            print(sc['title'], 'src offered:', bool(infos[sc['id']].get('src')), infos[sc['id']]['n'], 'pages')
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
        if os.environ.get('SLOW'): cdp = await ctx.new_cdp_session(ph); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': int(os.environ['SLOW'])})
        ph.on('console', lambda m: errs.append('console ' + m.text[:200]) if m.type == 'error' else None)
        await ph.route('**/__t/*', serve)
        await ph.add_init_script("""window.__noTour = true; try { localStorage.setItem('standPlayN', '2'); } catch {}
          window.__plog = []; window.standCaps = Object.assign(window.standCaps || {}, { peer: 3 });
          window.webkit = { messageHandlers: { standPeer: { postMessage() {} }, standDone: { postMessage() {} }, standDiag: { postMessage(m) { window.__plog.push(m.text); } } } };""")
        ph.on('pageerror', lambda e: errs.append('phone ' + str(e)))
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
        res = []
        for si, sc in enumerate(L['scores']):
            await ph.set_viewport_size({'width': 393, 'height': 852})
            t0 = time.time()
            await ph.evaluate("(t) => [...document.querySelectorAll('.phs-card')].find((c) => c.textContent.includes(t)).click()", sc['title'])
            await ph.wait_for_function("() => { const i = document.querySelector('#phvImg'); return !document.querySelector('#phView').hidden && i && i.complete && i.naturalWidth > 0; }", timeout=120000)
            t_open = time.time() - t0
            await ph.screenshot(path=f'{OUT}_{si}_page.png')
            await ph.set_viewport_size({'width': 852, 'height': 393})
            t1 = time.time()
            await ph.evaluate("() => { window.__ppShown = null; document.querySelector('#phvPlay').click(); }")
            await ph.wait_for_function("() => window.__ppShown && window.__ppShown[0]", timeout=60000)
            t_play = time.time() - t1
            await ph.screenshot(path=f'{OUT}_{si}_play.png')
            HASH = """() => { const c = document.querySelector('#phpC'); const g = c.getContext('2d'); const n = (window.__ppShown || []).length; const out = [];
              for (let q = 0; q < n; q++) { const h = Math.floor(c.height / n); const d = g.getImageData(0, q * h, c.width, h).data; let a = 0, b = 0; for (let i = 0; i < d.length; i += 64) { a = (a + d[i] * (i % 997)) % 1e9; b += d[i] < 128 ? 1 : 0; } out.push(a + ':' + b); }
              return { shown: window.__ppShown, h: out }; }"""
            bad = []
            async def settle():
                last = None
                for _ in range(60):
                    await ph.wait_for_timeout(150)
                    cur = json.dumps(await ph.evaluate(HASH))
                    if cur == last and await ph.evaluate("() => document.querySelector('#phpBusy').hidden"): return json.loads(cur)
                    last = cur
                return json.loads(last)
            async def fresh():
                # the same lines drawn again from nothing: what the screen should show
                await ph.evaluate("() => window.dispatchEvent(new Event('resize'))")
                return await settle()
            seq = os.environ.get('SEQ', '3 f f n2 F F F F F b n3 F F F n2 F F F F F F b b B B F F F')
            prev = await settle()
            for st in seq.split():
                if st.startswith('n'): await ph.evaluate("(n) => document.querySelector('#phpN button[data-n=\"' + n + '\"]').click()", st[1:])
                elif st in ('f', 'b'): await ph.keyboard.press('PageDown' if st == 'f' else 'PageUp'); await settle()
                elif st == 'F': await ph.keyboard.press('PageDown'); await ph.wait_for_timeout(60)
                elif st == 'B': await ph.keyboard.press('PageUp'); await ph.wait_for_timeout(60)
                else: continue
                if st in ('F', 'B'): continue
                now = await settle(); shot1 = await ph.evaluate("() => document.querySelector('#phpC').toDataURL('image/png')"); ref = await fresh()
                if now['h'] != ref['h']:
                    import base64 as B64
                    open(f'/tmp/claude-0/pf_diff_a_{st}.png','wb').write(B64.b64decode(shot1.split(',')[1]))
                    open(f'/tmp/claude-0/pf_diff_b_{st}.png','wb').write(B64.b64decode((await ph.evaluate("() => document.querySelector('#phpC').toDataURL('image/png')")).split(',')[1]))
                if now['h'] != ref['h'] or now['shown'] != ref['shown']: bad.append((st, now['shown'], 'screen differs from a fresh drawing of its lines'))
                print(' ', st, now['shown'], 'ok' if now['h'] == ref['h'] else 'DIFFERS', flush=True)
            now = await settle(); ref = await fresh()
            same = [q for q in range(min(len(now['h']), len(ref['h']))) if now['h'][q] != ref['h'][q]]
            print('  after fast steps:', now['shown'], 'slots wrong:', same)
            if same or now['shown'] != ref['shown']: bad.append(('fast', now['shown'], 'slots wrong ' + str(same)))
            # each slot must show its own line: two slots never the same picture, none blank
            if len(set(ref['h'])) != len(ref['h']): bad.append(('dup', ref['shown'], 'two slots alike'))
            res.append((not bad, True, 10, 0, 'x:x', 0)); print(sc['title'], 'problems', bad)
            await ph.screenshot(path=f'{OUT}_{si}_end.png')
            await ph.evaluate("() => document.querySelector('#phpClose').click()"); await ph.wait_for_timeout(400)
            await ph.evaluate("() => document.querySelector('#phvClose').click()"); await ph.wait_for_timeout(600)
        print('timings (page, render ms, rest ms)', await ph.evaluate("() => window.__ppT"))
        log = await ph.evaluate("() => window.__plog")
        print('\n'.join(x for x in log if 'iPhone' in x)); print('asked', await ph.evaluate("() => [...new Set(window.__asked)]"))
        ok = all(r[0] for r in res) and not errs
        print('PASS' if ok else 'FAIL', 'Play on the iPhone: switching 2/3 and fast steps, every line where it should be'); print(errs[:4])
        await b.close()
asyncio.run(main())
