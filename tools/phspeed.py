# iPad → iPhone: how long a score takes to come, with a simulated link (the iPad draws one page at a
# time, 200 ms each; the answer takes 150 ms to travel)
import asyncio, json, os
from playwright.async_api import async_playwright
PDF='/home/claude/fixtures/vector8.pdf'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ipad = await (await b.new_context(viewport={'width':1180,'height':820})).new_page()
        await ipad.add_init_script('window.__noTour = true;'); errs=[]
        await ipad.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await ipad.wait_for_timeout(1200)
        await ipad.evaluate("() => document.querySelector('#welGo')?.click()")
        await ipad.set_input_files('#importInput', PDF); await ipad.wait_for_timeout(5000)
        lst = await ipad.evaluate("async () => JSON.stringify(await window.__answerPhone({ what: 'list' }))")
        sid = json.loads(lst)['scores'][0]['id']
        one = await ipad.evaluate("async (id) => { const info = await window.__answerPhone({ what: 'scoreinfo', id }); const pages = []; for (let i = 0; i < info.n; i++) pages.push(await window.__answerPhone({ what: 'page', id, i })); return JSON.stringify({ info, pages }); }", sid)
        ph = await (await b.new_context(viewport={'width':393,'height':852}, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).new_page()
        await ph.add_init_script('window.__noTour = true;'); ph.on('pageerror', lambda e: errs.append(str(e)))
        await ph.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.evaluate("""(a) => { const [l, o] = a; const O = JSON.parse(o); let q0 = Promise.resolve(); const sl = (ms) => new Promise(r => setTimeout(r, ms)); window.__maxAt = 0; let at = 0;
          window.__askIpadTest = async (q) => { if (q.what === 'list') return JSON.parse(l); await sl(150); at++; window.__maxAt = Math.max(window.__maxAt, at);
            const job = q0.then(() => sl(q.what === 'page' ? 200 : 20)); q0 = job; await job; await sl(150); at--; return q.what === 'scoreinfo' ? O.info : O.pages[q.i]; }; }""", [lst, one])
        t = await ph.evaluate("""async () => { const t0 = performance.now(); document.querySelector('#phScoresBar').click();
          const { db } = await import('/js/db.js');
          for (let k = 0; k < 400; k++) { await new Promise(r => setTimeout(r, 50)); const ks = (await db.keys('files')).map(String); if (ks.some(x => x.startsWith('ipadcopy:') && !x.includes(':s'))) return [Math.round(performance.now() - t0), ks.filter(x => x.startsWith('ipadcopy:')).length, window.__maxAt]; } return 'timeout'; }""")
        print('pages', json.loads(one)['info']['n'], 'ms, keys, most at once', t, errs[:3]); await b.close()
asyncio.run(main())
