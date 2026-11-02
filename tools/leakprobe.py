# Which listeners pile up when the same things are done again and again (open and close scores,
# notebooks, Compose, panels)? Each addEventListener is counted by where in the code it was made;
# the counts after round 2 and after round 8 are compared. Also canvases and DOM nodes.
import asyncio, os, re
from playwright.async_api import async_playwright
FIX = '/home/claude/fixtures/'
WRAP = r"""
(() => {
  const live = new Map(); window.__listeners = live;
  const where = () => { const s = (new Error().stack || '').split('\n').map((l) => l.trim()).filter((l) => /\/js\//.test(l)); const l = s[1] || s[0] || '?'; const m = /\/js\/([^:?]+):(\d+)/.exec(l); return m ? m[1] + ':' + m[2] : l.slice(0, 60); };
  const add0 = EventTarget.prototype.addEventListener, rem0 = EventTarget.prototype.removeEventListener;
  const tag = (t) => t === window ? 'window' : t === document ? 'document' : t && t.nodeType === 1 ? (t.id ? '#' + t.id : t.tagName.toLowerCase() + (t.className && typeof t.className === 'string' ? '.' + t.className.split(' ')[0] : '')) : (t && t.constructor && t.constructor.name) || '?';
  const refs = new WeakMap();
  EventTarget.prototype.addEventListener = function (type, fn, o) {
    if (fn) { let m = refs.get(this); if (!m) { m = new Map(); refs.set(this, m); } const k = type + '|' + (typeof fn === 'function' ? fn : fn.handleEvent); if (!m.has(k)) { const key = where() + ' ' + type + ' on ' + (this.isConnected === false ? '(detached) ' : '') + tag(this); m.set(k, key); live.set(key, (live.get(key) || 0) + 1); } }
    return add0.call(this, type, fn, o);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, o) {
    const m = refs.get(this); const k = type + '|' + (typeof fn === 'function' ? fn : fn && fn.handleEvent);
    if (m && m.has(k)) { const key = m.get(k); m.delete(k); live.set(key, (live.get(key) || 1) - 1); }
    return rem0.call(this, type, fn, o);
  };
})();
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1366, 'height': 1024}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(WRAP)
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', [FIX + 'vector8.pdf', FIX + 'scan10.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 2", timeout=60000)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); " + js + " }")
        ROUND = """
          const cards = () => [...document.querySelectorAll('#grid .card:not(.folder)')];
          for (const i of [0, 1]) {
            cards()[i].click(); await sleep(1800);
            document.querySelector('#inkBtn').click(); await sleep(300); document.querySelector('#inkBtn').click(); await sleep(200);
            for (const pn of ['metronome', 'tuner', 'takes', 'settings', 'passages', 'listen', 'reps', 'scales']) { document.querySelector('#score [data-panel="' + pn + '"]')?.click(); await sleep(350); for (const c of document.querySelectorAll('aside.panel:not([hidden]) [data-close]')) c.click(); await sleep(150); }
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); await sleep(300);
            document.querySelector('#backBtn').click(); await sleep(900);
          }
          for (const pn of ['app', 'backup', 'goal']) { document.querySelector('[data-panel="' + pn + '"]')?.click(); await sleep(400); for (const c of document.querySelectorAll('aside.panel:not([hidden]) [data-close]')) c.click(); await sleep(150); }
          const E = await import('/js/compose/editor.js'); await E.createComposition({ title: 'L', insts: ['cello'], time: [4, 4], bars: 4 }); await sleep(1200); document.querySelector('#cpBack').click(); await sleep(900);
        """
        snap = "return [Object.fromEntries([...window.__listeners].filter(([, v]) => v > 0)), document.querySelectorAll('*').length, document.querySelectorAll('canvas').length]"
        for r in range(2): await J(ROUND)
        a, na, ca = await J(snap)
        for r in range(6): await J(ROUND)
        z, nz, cz = await J(snap)
        grow = sorted(((z.get(k, 0) - a.get(k, 0), k) for k in set(z) | set(a)), reverse=True)
        print('nodes', na, '->', nz, 'canvases', ca, '->', cz)
        print('listeners growing over 6 rounds:')
        for d, k in grow[:25]:
            if d > 0: print(' ', d, k)
        await b.close()
asyncio.run(main())
