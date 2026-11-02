# iPhone My scores: everything downloaded at once, taken off the iPhone and brought back, folders from
# the iPad, a new folder by dragging one score onto another, into and out of folders
import asyncio, json, copy
from playwright.async_api import async_playwright
S = '/home/claude/shots/'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        await ipad.add_init_script('window.__noTour = true;')
        errs=[]; ipad.on('pageerror', lambda e: errs.append('ipad '+str(e)))
        await ipad.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', '/home/claude/fixtures/vector8.pdf'); await ipad.wait_for_timeout(5000)
        L = json.loads(await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))"))
        one = await ipad.evaluate("async (id) => { const info = await window.__answerPhone({ what: 'scoreinfo', id }); const pages = []; for (let i = 0; i < info.n; i++) pages.push(await window.__answerPhone({ what: 'page', id, i })); return JSON.stringify({ info, pages }); }", L['scores'][0]['id'])
        base = L['scores'][0]; lst = []
        names = [('Suite No. 1', 'Bach', 'f1', 'Bach suites'), ('Suite No. 2', 'Bach', 'f1', 'Bach suites'), ('Sonata', 'Brahms', '', ''), ('Concerto', 'Elgar', '', ''), ('Requiebros', 'Cassadó', '', '')]
        for i, (t, c, fid, fn) in enumerate(names):
            x = copy.deepcopy(base); x.update(id='s%d' % i, title=t, composer=c, fid=fid, folder=fn, stamp=1000 + i); lst.append(x)
        LS = json.dumps({'v': 1, 'at': 1, 'scores': lst})
        ph = await (await b.new_context(viewport={'width':393,'height':852}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).new_page()
        await ph.add_init_script('window.__noTour = true;')
        ph.on('pageerror', lambda e: errs.append('phone '+str(e)))
        await ph.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.evaluate("(a) => { const [l, o] = a; window.__asked = []; window.__askIpadTest = async (q) => { window.__asked.push(q.what + (q.id || '')); await new Promise(r => setTimeout(r, 120)); const O = JSON.parse(o); return q.what === 'list' ? JSON.parse(l) : q.what === 'scoreinfo' ? { ...O.info, id: q.id, stamp: undefined } : O.pages[q.i]; }; }", [LS, one])
        J = lambda js: ph.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        await J("document.querySelector('#phScoresBar').click(); await sleep(4000);")
        copies = "const { db } = await import('/js/db.js'); return (await db.keys('files')).filter(k => String(k).startsWith('ipadcopy:')).map(k => String(k).slice(9)).sort().join(',')"
        print('asked', await J("return window.__asked.join(' ')"))
        print('downloaded', await J(copies))
        cards = "return [...document.querySelectorAll('#phsGrid .phs-card')].map(c => (c.classList.contains('phs-folder') ? '[' : '') + c.querySelector('.phs-t').textContent + (c.querySelector('.phs-state') ? ':' + c.querySelector('.phs-state').className.split(' ')[1] : ''))"
        print('top', await J(cards), await J("return document.querySelector('#phsSub').textContent"))
        await ph.screenshot(path=S + 'phf_top.png')
        # open the folder
        await J("document.querySelector('.phs-folder').click(); await sleep(300);")
        print('in folder', await J("return document.querySelector('#phsTitle').textContent"), await J(cards))
        await J("document.querySelector('#phsClose').click(); await sleep(300);")
        # remove one, then bring back
        await J("document.querySelector('#phsEdit').click(); await sleep(200);")
        await ph.screenshot(path=S + 'phf_edit.png')
        await J("[...document.querySelectorAll('.phs-card[data-score]')].find(c => /Concerto/.test(c.textContent)).querySelector('.phs-del').click(); await sleep(300); document.querySelector('#phsSheetOk').click(); await sleep(400);")
        print('after remove', await J(cards), await J(copies), await J("return document.querySelector('#phsRemovedText').textContent"))
        await J("document.querySelector('#phsEdit').click(); await sleep(200);")
        # drag Sonata onto Requiebros: new folder
        async def drag(src_sel, dst_sel):
            a = await J(f"const r = {src_sel}.getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/3]")
            z = await J(f"const r = {dst_sel}.getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/3]")
            await ph.mouse.move(*a); await ph.mouse.down(); await ph.wait_for_timeout(520)
            for i in range(1, 11): await ph.mouse.move(a[0] + (z[0] - a[0]) * i / 10, a[1] + (z[1] - a[1]) * i / 10); await ph.wait_for_timeout(30)
            await ph.mouse.up(); await ph.wait_for_timeout(500)
        card = lambda t: f"[...document.querySelectorAll('.phs-card')].find(c => c.querySelector('.phs-t').textContent === '{t}')"
        await drag(card('Sonata'), card('Requiebros'))
        print('sheet', await J("return [!document.querySelector('#phsSheet').hidden, document.querySelector('#phsSheetTitle').textContent, document.querySelector('#phsSheetName').value]"))
        await J("document.querySelector('#phsSheetName').value = 'Spanish & German'; document.querySelector('#phsSheetOk').click(); await sleep(400);")
        print('after new folder', await J(cards))
        # drag a Bach out of its folder: open folder, drag to the drop zone
        await J(card('Bach suites') + ".click(); await sleep(300);")
        a = await J('return ' + card('Suite No. 2') + ".getBoundingClientRect().toJSON()")
        await ph.mouse.move(a['x'] + 40, a['y'] + 40); await ph.mouse.down(); await ph.wait_for_timeout(520)
        await ph.mouse.move(a['x'] + 60, a['y'] + 20); await ph.wait_for_timeout(100)
        o = await J("const r = document.querySelector('#phsOut').getBoundingClientRect(); return [document.querySelector('#phsOut').hidden, r.left + r.width/2, r.top + r.height/2]")
        print('out zone shown', not o[0])
        await ph.screenshot(path=S + 'phf_drag.png')
        await ph.mouse.move(o[1], o[2], steps=6); await ph.wait_for_timeout(100); await ph.mouse.up(); await ph.wait_for_timeout(500)
        print('folder after out', await J(cards))
        await J("document.querySelector('#phsClose').click(); await sleep(300);")
        print('top after', await J(cards))
        # and into the new folder
        await drag(card('Suite No. 2'), card('Spanish & German'))
        print('top after into', await J(cards))
        await J("document.querySelector('#phsRemoved button').click(); await sleep(1500);")
        print('brought back', await J(cards), await J(copies))
        # the arrangement stays when the list comes again
        await J("document.querySelector('#phsRefresh').click(); await sleep(1500);")
        print('after refresh', await J(cards))
        await ph.screenshot(path=S + 'phf_final.png')
        print(errs); await b.close()
asyncio.run(main())
