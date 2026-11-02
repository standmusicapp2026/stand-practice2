# Play on the iPhone through a whole score: every line, to the end; 2 then 3 lines; another score after
import asyncio, json, os, sys
from playwright.async_api import async_playwright
OUT = '/tmp/claude-0/nav'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        await ipad.add_init_script('window.__noTour = true; window.OffscreenCanvas = undefined;')
        errs=[]; ipad.on('pageerror', lambda e: errs.append('ipad '+str(e)))
        await ipad.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', sys.argv[1:3]); await ipad.wait_for_timeout(9000)
        L = json.loads(await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))"))
        print('scores', [(x['title'], x['pages']) for x in L['scores']])
        data = {}
        for sc in L['scores']:
            sid = sc['id']
            info = await ipad.evaluate("async (id) => window.__answerPhone({ what: 'scoreinfo', id })", sid)
            pages = await ipad.evaluate("async (id) => { const info = await window.__answerPhone({ what: 'scoreinfo', id }); const out = []; for (let i = 0; i < info.n; i++) out.push(await window.__answerPhone({ what: 'page', id, i })); return JSON.stringify(out); }", sid)
            lines = await ipad.evaluate("async (id) => { const info = await window.__answerPhone({ what: 'scoreinfo', id }); const out = []; for (let i = 0; i < info.n; i++) out.push(await window.__answerPhone({ what: 'lines', id, i })); return JSON.stringify(out); }", sid)
            data[sid.split(':')[-1] if False else sid] = {'info': info, 'pages': json.loads(pages), 'lines': json.loads(lines)}
            print(sc['title'], 'lines per page', [len(x['lines']) for x in json.loads(lines)])
        ph = await (await b.new_context(viewport={'width':852,'height':393}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).new_page()
        await ph.add_init_script("window.__noTour = true; window.OffscreenCanvas = undefined; try { localStorage.setItem('standPlayN', '2'); } catch {}")
        ph.on('pageerror', lambda e: errs.append('phone '+str(e)))
        await ph.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.evaluate("(a) => { const [l, d] = a; const D = JSON.parse(d); window.__D = D; const key = (id) => Object.keys(D).find((k) => k.endsWith(id) || id.endsWith(k) || k.slice(9) === id || k === id); window.__askIpadTest = async (q) => { if (q.what === 'list') return JSON.parse(l); const S = D[key(q.id)]; return q.what === 'scoreinfo' ? S.info : q.what === 'lines' ? S.lines[q.i] : S.pages[q.i]; }; }", [json.dumps(L), json.dumps(data)])
        await ph.set_viewport_size({'width': 393, 'height': 852})
        await ph.evaluate("() => document.querySelector('#phScoresBar').click()"); await ph.wait_for_timeout(1200)
        res = {}
        for si, title in enumerate([x['title'] for x in L['scores']]):
            await ph.set_viewport_size({'width': 393, 'height': 852})
            await ph.wait_for_function("(t) => [...document.querySelectorAll('.phs-card')].some((c) => c.textContent.includes(t))", arg=title, timeout=30000)
            await ph.evaluate("(t) => [...document.querySelectorAll('.phs-card')].find((c) => c.textContent.includes(t)).click()", title); await ph.wait_for_timeout(2500)
            await ph.set_viewport_size({'width': 852, 'height': 393})
            await ph.evaluate("() => document.querySelector('#phvPlay').click()"); await ph.wait_for_timeout(3500)
            await ph.screenshot(path=f'{OUT}_{si}_first.png')
            seen = []
            for k in range(80):
                w = await ph.evaluate("() => document.querySelector('#phpWhere').textContent")
                seen.append(w)
                await ph.keyboard.press('PageDown'); await ph.wait_for_timeout(700)
                last = seen[-1].split(' of ')
                if len(last) == 2 and last[0].endswith(last[1]) and len(seen) > 8 and len(set(seen[-8:])) == 1: break
            await ph.screenshot(path=f'{OUT}_{si}_end.png')
            # three lines, and back two screens
            await ph.evaluate("() => document.querySelector('#phpN button[data-n=\"3\"]').click()"); await ph.wait_for_timeout(1500)
            await ph.screenshot(path=f'{OUT}_{si}_three.png')
            await ph.keyboard.press('PageUp'); await ph.wait_for_timeout(900); await ph.keyboard.press('PageUp'); await ph.wait_for_timeout(900)
            await ph.screenshot(path=f'{OUT}_{si}_three_back.png')
            await ph.evaluate("() => document.querySelector('#phpN button[data-n=\"2\"]').click()"); await ph.wait_for_timeout(1200)
            print(title, 'pages reached', sorted(set(seen), key=lambda x: seen.index(x)), 'steps', len(seen))
            await ph.evaluate("() => document.querySelector('#phpClose').click()"); await ph.wait_for_timeout(500)
            await ph.evaluate("() => document.querySelector('#phvClose').click()"); await ph.wait_for_timeout(800)
        print(errs[:5]); await b.close()
asyncio.run(main())
