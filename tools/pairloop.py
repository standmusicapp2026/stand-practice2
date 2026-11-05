# Settings open on the iPad and the iPhone, with the app answering as the real one does: the card of
# linked devices is drawn once, not again and again (a card redrawn without end made iOS take no tap
# on any button in Settings)
import asyncio, os
from playwright.async_api import async_playwright
NAT = '''window.__noTour = true; window.__asks = 0; window.standCaps = { native: true, face: true, tap: true, pencil: true, video: true, audio: true, files: 3, busy: 1, peer: 4, notify: 1 };
  window.webkit = { messageHandlers: new Proxy({}, { get: (t, k) => t[k] || (t[k] = { postMessage(m) {
    if (k === 'standPeer' && m && m.op === 'pairList') { window.__asks++; setTimeout(() => window.standPairEvent && window.standPairEvent('list', { list: [{ d: 'dev1', kind: 'iPhone', at: 1793000000000 }], me: 'iPad' }), 15); } } }) }) };'''
async def main():
    res = []
    async with async_playwright() as p:
        for phone in (False, True):
            b = await getattr(p, os.environ.get('BR', 'chromium')).launch()
            kw = dict(viewport={'width': 393, 'height': 852}, is_mobile=True, has_touch=True, user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)') if phone else dict(viewport={'width': 1180, 'height': 820}, has_touch=True)
            pg = await (await b.new_context(**kw)).new_page(); await pg.add_init_script(NAT)
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
            await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); try { localStorage.setItem('standLinkIntro', '1'); } catch {} }"); await pg.wait_for_timeout(900)
            r = await pg.evaluate("""async () => { const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
              document.querySelector('[data-panel="app"]').click(); await sleep(800);
              const card = document.querySelector('#pairCard'); let n = 0; const mo = new MutationObserver((l) => { n += l.length; }); mo.observe(document.querySelector('#panel-app'), { subtree: true, childList: true, characterData: true, attributes: true });
              const a0 = window.__asks; await sleep(3000); mo.disconnect();
              return { changes: n, asks: window.__asks - a0, shown: card.querySelector('.pair-list').textContent }; }""")
            ok = r['changes'] < 10 and r['asks'] < 4 and 'iPhone' in r['shown']
            res.append(ok and not errs)
            print('PASS' if ok else 'FAIL', 'iPhone' if phone else 'iPad', f"Settings open 3 s: {r['changes']} changes, asked for the list {r['asks']} times; shows: {r['shown']!r}", errs[:2], flush=True)
            await b.close()
    print('PASS' if all(res) else 'FAIL', 'the linked devices card is drawn once, Settings stay still')
asyncio.run(main())
