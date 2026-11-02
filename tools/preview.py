import asyncio, json, urllib.parse as U
from playwright.async_api import async_playwright
HTML = '<div id="tabScore1"><div class="we"><table class="we_edition_info"><tr><th>Editor</th><td>Becker</td></tr></table><div id="IMSLP4242"><a class="internal" href="/images/x/PMLP99-Kol_Nidrei.pdf">f</a><span class="we_file_download"><a href="#"><span title="dl">Complete Score</span></a></span><span title="Total number of downloads: 1234">1</span><span class="we_file_info2">12 pp. 1.2 MB</span></div></div></div>'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width':1366,'height':1024})).new_page()
        await pg.add_init_script("window.__noTour = true; try{localStorage.setItem(\"x\",\"1\")}catch(e){}; window.webkit = { messageHandlers: { standOpen: { postMessage(m) { window.__opened = m; } } } };")
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def api(route):
            q = dict(U.parse_qsl(U.urlparse(route.request.url).query)); cb=q['callback']
            if q.get('action')=='parse': d={'parse':{'title':'Kol Nidrei, Op.47 (Bruch, Max)','text':{'*':HTML}}}
            elif q.get('list')=='categorymembers': d={'query':{'categorymembers':[{'title':'Kol Nidrei, Op.47 (Bruch, Max)'}]}}
            else: d={'query':{'search':[]}}
            await route.fulfill(content_type='text/javascript', body=f'{cb}({json.dumps(d)})')
        await pg.route('https://imslp.org/api.php*', api)
        await pg.route('**/__in/kol.pdf', lambda r: r.fulfill(path='/home/claude/fixtures/titles/c.pdf', content_type='application/pdf'))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { const w=document.querySelector('#welcome'); if (w && !w.hidden) document.querySelector('#welGo')?.click(); setTimeout(()=>document.querySelector('.tour-skip')?.click(),300); }"); await pg.wait_for_timeout(900)
        await pg.evaluate("() => { document.querySelector('[data-tab=\"find\"], #tab-find')?.click(); }"); await pg.wait_for_timeout(300)
        await pg.evaluate("() => { const i=document.querySelector('#findInput'); i.value='bruch kol nidrei'; document.querySelector('#findForm').requestSubmit(); }"); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => document.querySelector('#workList button').click()"); await pg.wait_for_timeout(1200)
        print('pick buttons', await pg.evaluate("() => [...document.querySelectorAll('#workPicks .pick-btns a')].map(a=>a.textContent)"))
        await pg.screenshot(path='/home/claude/shots/find_preview.png')
        await pg.evaluate("() => document.querySelector('#workPicks .pick-btns a').click()")
        print('opened', await pg.evaluate("() => window.__opened"))
        await pg.evaluate("() => window.standIncoming({ path: '/__in/kol.pdf', name: 'PMLP99-Kol_Nidrei.pdf', meta: { title: 'Kol Nidrei, Op.47', composer: 'Max Bruch' } })")
        await pg.wait_for_timeout(3000)
        st = await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return { bar: !document.querySelector('#previewBar').hidden, scoreOpen: !document.querySelector('#score').hidden, scores: (await db.all('scores')).map(s=>[s.title, !!s.preview]), grid: document.querySelectorAll('#grid .card:not(.folder)').length } }")
        print('after incoming', st)
        await pg.screenshot(path='/home/claude/shots/preview_open.png')
        await pg.evaluate("() => document.querySelector('#previewRemove').click()"); await pg.wait_for_timeout(1500)
        print('after remove', await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return { scores: (await db.all('scores')).length, files: (await db.all('files')).length } }"))
        # keep path
        await pg.evaluate("() => { document.querySelector('#tab-find, [data-tab=\"find\"]')?.click(); document.querySelector('#workPicks .pick-btns a').click(); }")
        await pg.evaluate("() => window.standIncoming({ path: '/__in/kol.pdf', name: 'PMLP99-Kol_Nidrei.pdf', meta: { title: 'Kol Nidrei, Op.47', composer: 'Max Bruch' } })"); await pg.wait_for_timeout(3000)
        await pg.evaluate("() => document.querySelector('#previewKeep').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(1200)
        print('after keep', await pg.evaluate("async () => { const { db } = await import('/js/db.js'); return { scores: (await db.all('scores')).map(s=>[s.title, !!s.preview]), grid: document.querySelectorAll('#grid .card:not(.folder)').length } }"))
        # add directly: no preview
        await pg.evaluate("() => { document.querySelector('#tab-find, [data-tab=\"find\"]')?.click(); document.querySelectorAll('#workPicks .pick-btns a')[1].click(); }")
        await pg.evaluate("() => window.standIncoming({ path: '/__in/kol.pdf', name: 'PMLP99-Kol_Nidrei.pdf', meta: { title: 'Kol Nidrei, Op.47', composer: 'Max Bruch' } })"); await pg.wait_for_timeout(3000)
        print('add: bar shown?', await pg.evaluate("() => !document.querySelector('#previewBar').hidden"))
        print(errs); await b.close()
asyncio.run(main())
