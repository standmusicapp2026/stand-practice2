import asyncio, json
from playwright.async_api import async_playwright
U='http://127.0.0.1:' + __import__('os').environ.get('PORT','8766') + '/index.html'
SETUP = """() => {
  const img = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  window.__T = { list: [{id:'A',title:'Alpha',composer:'',pages:4,folder:'',fid:'',stamp:1,thumb:null},{id:'B',title:'Beta',composer:'',pages:4,folder:'',fid:'',stamp:1,thumb:null}], stamp: {A:1,B:1}, n: {A:4,B:4}, delay: 0, fail: null, ver: {A:'v1',B:'v1'}, asked: [] };
  window.__askIpadTest = async (q) => {
    const T = window.__T; T.asked.push(JSON.stringify(q));
    if (T.delay) await new Promise(r => setTimeout(r, T.delay));
    if (T.fail && T.fail(q)) throw new Error('gone');
    if (q.what === 'list') return { v:1, scores: JSON.parse(JSON.stringify(T.list)) };
    if (q.what === 'scoreinfo') return { v:2, id:q.id, n:T.n[q.id], stamp:T.stamp[q.id] };
    return { v:2, id:q.id, i:q.i, w:10, h:10, img, ink: null, ver: T.ver[q.id] };
  };
}"""
KEYS = "async () => { const { db } = await import('/js/db.js'); return (await db.keys('files')).map(String).filter(k => k.startsWith('ipadcopy:')).sort(); }"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ph = await (await b.new_context(viewport={'width':393,'height':852}, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).new_page()
        await ph.add_init_script('window.__noTour = true;')
        errs=[]; ph.on('pageerror', lambda e: errs.append(str(e)))
        await ph.add_init_script(SETUP.join(['(', ')();']) if False else '(' + SETUP + ')();')
        await ph.goto(U); await ph.wait_for_timeout(1500)
        await ph.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await ph.wait_for_timeout(3000)
        print('1 after first sync', await ph.evaluate(KEYS))
        # --- remove a score while it is being downloaded
        await ph.evaluate("() => { __T.stamp.A = 2; __T.list[0].stamp = 2; __T.delay = 150; }")
        await ph.evaluate("() => document.querySelector('#phScoresBar').click()"); await ph.wait_for_timeout(700)
        await ph.evaluate("() => document.querySelector('#phsEdit').click()"); await ph.wait_for_timeout(200)
        await ph.evaluate("() => document.querySelector('.phs-card[data-score=A] .phs-del').click()")
        await ph.wait_for_timeout(3000)
        print('2 A removed during its download; keys:', await ph.evaluate(KEYS))
        await ph.evaluate("() => { __T.delay = 0; }")
        await ph.evaluate("() => document.querySelector('#phsBringBack').click()"); await ph.wait_for_timeout(2500)
        print('2b after Bring back:', await ph.evaluate(KEYS), await ph.evaluate("() => [...document.querySelectorAll('.phs-card[data-score=A] .phs-state')].map(e => e.className)"))
        await ph.evaluate("() => document.querySelector('.phs-card[data-score=A]').click()"); await ph.wait_for_timeout(1500)
        print('2c viewer:', await ph.evaluate("() => [document.querySelector('#phView').hidden, document.querySelector('#phvPage').textContent, document.querySelector('#phvImg').getAttribute('src')]"))
        await ph.evaluate("() => document.querySelector('#phvClose').click()")
        # orphan folder: score placed (on iPhone) in an iPad folder that the iPad then removes
        await ph.evaluate("() => { __T.list[1].fid='F1'; __T.list[1].folder='Bach'; __T.list[0].fid='F1'; __T.list[0].folder='Bach'; }")
        await ph.evaluate("() => window.__phs.refresh(true)"); await ph.wait_for_timeout(1500)
        await ph.evaluate("async () => { const { getSetting, setSetting } = await import('/js/db.js'); }")
        # simulate the drag: put B into ipad:F1 explicitly (as a drag on the phone would) then the iPad dissolves folder F1
        await ph.evaluate("async () => { const { db } = await import('/js/db.js'); }")
        print('folders before', await ph.evaluate("() => [...document.querySelectorAll('.phs-folder .phs-t')].map(e=>e.textContent)"))
        print('errs', errs[:5]); await b.close()
asyncio.run(main())
