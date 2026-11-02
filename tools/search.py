import asyncio, json, urllib.parse as U
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        log=[]
        async def api(route):
            q = dict(U.parse_qsl(U.urlparse(route.request.url).query)); cb=q['callback']; log.append({k:q[k] for k in q if k!='callback'})
            if q.get('list')=='search' and q.get('srnamespace')=='14':
                d={'query':{'search':[{'title':'Category:Zzyzx, Hannelore Maria'}]}}
            elif q.get('list')=='search':
                d={'query':{'search':[{'title':'Ballade No.2 (Zzyzx, Hannelore Maria)','snippet':''}]}}
            elif q.get('list')=='categorymembers':
                d={'query':{'categorymembers':[{'title':'Ballade No.1 (Zzyzx, Hannelore Maria)'},{'title':'Elegy for Cello (Zzyzx, Hannelore Maria)'},{'title':'Sonata in D (Zzyzx, Hannelore Maria)'}]}}
            else: d={}
            await route.fulfill(content_type='text/javascript', body=f'{cb}({json.dumps(d)})')
        await pg.route('https://imslp.org/api.php*', api)
        await pg.route('https://www.wikidata.org/**', lambda r: r.fulfill(content_type='application/json', body='{"query":{"search":[]}}'))
        await pg.goto('http://localhost:' + __import__('os').environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1000)
        for q in ['zzyzx', 'zzyzx elegy cello', 'ballade cello']:
            r = await pg.evaluate("async (q) => { const m = await import('/js/imslp.js'); const r = await m.searchWorks(q); return { comp: r.composer && r.composer.n, browse: r.browse, res: r.results.map(x=>x.title) }; }", q)
            print(q, '->', r)
        print([l.get('srsearch') or l.get('cmtitle') for l in log])
        await b.close()
asyncio.run(main())
