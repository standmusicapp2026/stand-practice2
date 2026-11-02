# The iPhone gets a score as its own PDF in one go (as over the direct link), draws its pages and
# Play's lines itself; Play goes through the whole score with no line shown twice or left behind,
# and every step is quick
import asyncio, json, os, sys, time
from playwright.async_api import async_playwright
FILES = sys.argv[1:] or ['/home/claude/real/muto/bwv1008-a4.pdf', '/home/claude/fixtures/imslp12.pdf']
OUT = '/tmp/claude-0/pf'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
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
            shown = [tuple(await ph.evaluate("() => window.__ppShown"))]
            steps = []
            for k in range(200):
                before = await ph.evaluate("() => JSON.stringify(window.__ppShown)")
                ts = time.time()
                await ph.keyboard.press('PageDown')
                try: await ph.wait_for_function("(b) => JSON.stringify(window.__ppShown) !== b", arg=before, timeout=8000)
                except Exception: break
                steps.append(time.time() - ts)
                shown.append(tuple(await ph.evaluate("() => window.__ppShown")))
            flat = [x for scr in shown for x in scr if x]
            dup = len(flat) - len(set(flat))
            order = all((int(a.split(':')[0]), int(a.split(':')[1])) < (int(b2.split(':')[0]), int(b2.split(':')[1])) for a, b2 in zip(flat, flat[1:]))
            last = flat[-1] if flat else None
            print(sc['title'], f'open {t_open:.1f}s play {t_play:.1f}s', 'screens', len(shown), 'lines', len(flat), 'dups', dup, 'in order', order, 'last', last, f'slowest step {max(steps) if steps else 0:.2f}s')
            res.append((dup == 0, order, len(flat), max(steps) if steps else 0, last, infos[sc['id']]['n']))
            await ph.screenshot(path=f'{OUT}_{si}_end.png')
            await ph.evaluate("() => document.querySelector('#phpClose').click()"); await ph.wait_for_timeout(400)
            await ph.evaluate("() => document.querySelector('#phvClose').click()"); await ph.wait_for_timeout(600)
        print('timings (page, render ms, rest ms)', await ph.evaluate("() => window.__ppT"))
        log = await ph.evaluate("() => window.__plog")
        print('\n'.join(x for x in log if 'iPhone' in x)); print('asked', await ph.evaluate("() => [...new Set(window.__asked)]"))
        ok = all(d and o and n > 4 and st < 3 and last and int(last.split(':')[0]) == pages - 1 for d, o, n, st, last, pages in res) and not [e for e in errs]
        print('PASS' if ok else 'FAIL', 'Play from the PDF on the iPhone'); print(errs[:4])
        await b.close()
asyncio.run(main())
