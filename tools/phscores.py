# iPhone "See my scores": the iPad's answer, carried to an iPhone page, read there
import asyncio, json
from playwright.async_api import async_playwright
S='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/lay'
PDF='/home/claude/fixtures/vector8.pdf'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        await ipad.add_init_script('window.__noTour = true;')
        errs=[]; ipad.on('pageerror', lambda e: errs.append('ipad '+str(e)))
        await ipad.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', PDF); await ipad.wait_for_timeout(5000)
        # a marking on page 1
        await ipad.evaluate("""async () => { const { db } = await import('/js/db.js'); const sc = (await db.all('scores'))[0]; await db.put('ink', { key: sc.id + ':0', items: [{ t: 'shape', k: 'circle', x: 0.5, y: 0.3, w: 0.3, h: 0.2, f: '', lc: '#d62828', lw: 0.006, a: 1, rot: 0 }] }); }""")
        lst = await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))")
        L = json.loads(lst); print('list', [(x['title'], x['pages'], len(x['thumb'] or '')) for x in L['scores']])
        sid = L['scores'][0]['id']
        one = await ipad.evaluate("async (id) => { const info = await window.__answerPhone({ what: 'scoreinfo', id }); const pages = []; for (let i = 0; i < info.n; i++) pages.push(await window.__answerPhone({ what: 'page', id, i })); return JSON.stringify({ info, pages }); }", sid)
        lines = await ipad.evaluate("async (id) => { const out = []; for (let i = 0; i < 3; i++) out.push(await window.__answerPhone({ what: 'lines', id, i })); return JSON.stringify(out); }", sid)
        LN = json.loads(lines); print('lines per page', [len(x['lines']) for x in LN], 'line px', [(l['w'], l['h']) for l in LN[0]['lines']][:3])
        O = json.loads(one); print('score pages', O['info']['n'], 'ink on', [i for i, p in enumerate(O['pages']) if p['ink']], 'biggest page', max(len(json.dumps(p)) for p in O['pages']))
        ph = await (await b.new_context(viewport={'width':393,'height':852}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).new_page()
        await ph.add_init_script('window.__noTour = true;')
        ph.on('pageerror', lambda e: errs.append('phone '+str(e)))
        await ph.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.evaluate("(a) => { const [l, o] = a; const O = JSON.parse(o); window.__askIpadTest = async (q) => (q.what === 'list' ? JSON.parse(l) : q.what === 'scoreinfo' ? O.info : q.what === 'lines' ? (window.__LN[q.i] || { lines: [] }) : O.pages[q.i]); }", [lst, one])
        await ph.evaluate("(x) => { window.__LN = JSON.parse(x); }", lines)
        await ph.wait_for_timeout(500)
        await ph.screenshot(path=S+'/ph_home.png')
        await ph.evaluate("() => document.querySelector('#phScoresBar').click()"); await ph.wait_for_timeout(1200)
        await ph.screenshot(path=S+'/ph_list.png')
        await ph.evaluate("() => document.querySelector('.phs-card').click()"); await ph.wait_for_timeout(2500)
        await ph.screenshot(path=S+'/ph_view.png')
        await ph.evaluate("() => document.querySelector('#phvInk').click()"); await ph.wait_for_timeout(500)
        print('ink toggled', await ph.evaluate("() => [document.querySelector('#phvInkImg').hidden, document.querySelector('#phvPage').textContent]"))
        await ph.mouse.click(330, 500); await ph.wait_for_timeout(500)
        print('next', await ph.evaluate("() => document.querySelector('#phvPage').textContent"))
        # zoom: a pinch made of two touches (the page grows); a tap while zoomed does not turn
        await ph.screenshot(path=S+'/ph_view2.png')
        pg0 = await ph.evaluate("() => document.querySelector('#phvPage').textContent")
        await ph.evaluate("""() => { const st = document.querySelector('#phvStage'); const ev = (t, id, x, y) => st.dispatchEvent(new PointerEvent(t, { pointerId: id, clientX: x, clientY: y, bubbles: true }));
          ev('pointerdown', 1, 150, 400); ev('pointerdown', 2, 250, 400); ev('pointermove', 1, 100, 400); ev('pointermove', 2, 300, 400); ev('pointerup', 1, 100, 400); ev('pointerup', 2, 300, 400); }""")
        await ph.wait_for_timeout(300)
        print('zoom', await ph.evaluate("() => document.querySelector('#phvPageBox').style.transform"))
        await ph.mouse.click(330, 500); await ph.wait_for_timeout(400)
        print('tap while zoomed keeps the page', pg0 == await ph.evaluate("() => document.querySelector('#phvPage').textContent"))
        # Play, sideways
        await ph.set_viewport_size({'width': 852, 'height': 393})
        await ph.evaluate("() => document.querySelector('#phvPlay').click()"); await ph.wait_for_timeout(2500)
        await ph.screenshot(path=S+'/ph_play1.png')
        w1 = await ph.evaluate("() => document.querySelector('#phpWhere').textContent")
        for k in range(4): await ph.keyboard.press('PageDown'); await ph.wait_for_timeout(1500)
        await ph.screenshot(path=S+'/ph_play2.png')
        print('play', w1, '->', await ph.evaluate("() => document.querySelector('#phpWhere').textContent"))
        await ph.evaluate("() => window.__phonePlay && window.__phonePlay.wink('left')"); await ph.wait_for_timeout(1200)
        await ph.evaluate("() => document.querySelector('#phpClose').click()"); await ph.wait_for_timeout(500)
        print('closed', await ph.evaluate("() => [document.querySelector('#phPlay').hidden, !!window.__phonePlay]"))
        print(errs); await b.close()
asyncio.run(main())
