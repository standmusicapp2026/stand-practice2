# A big file (a long video) is shared by writing it to the app in pieces (never as one huge text);
# a small one as before. The app's side is played by a stub that answers like the real one.
import asyncio, os
from playwright.async_api import async_playwright
PORT = os.environ.get('PORT', '8765')
NAT = """window.__msgs = []; window.standCaps = Object.assign(window.standCaps || {}, { native: true, files: 4 });
window.webkit = { messageHandlers: new Proxy({}, { get: (t, k) => t[k] || (t[k] = { postMessage(m) {
  const short = { ...m }; if (short.data) short.data = short.data.length; window.__msgs.push([String(k), short]);
  if (k === 'standSave') { if (m.op === 'chunk') setTimeout(() => window.standSavedChunk({ id: m.id }), 5); if (m.op === 'end') setTimeout(() => window.standSaved({ id: m.id, ok: true, path: '' }), 5); }
} }) }) };"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(NAT)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        r = await pg.evaluate("""async () => { const sh = window.__standShareTest; return !!sh; }""")
        # through the Recordings export of an imported video would need a real video: call the share
        # path the same way the app does (shareBlob is not exported): via the Studio/backup hooks
        res = await pg.evaluate("""async () => {
          const big = new Blob([new Uint8Array(20e6)], { type: 'video/mp4' }), small = new Blob([new Uint8Array(1e5)], { type: 'video/mp4' });
          window.__msgs = []; await window.__shareBlob(big, 'Long video.mp4');
          const a = window.__msgs.slice(); window.__msgs = []; await window.__shareBlob(small, 'Short.mp4'); const c = window.__msgs.slice();
          return { big: a.map((m) => m[0] + ':' + (m[1].op || '') + (m[1].share ? '+share' : '')), small: c.map((m) => m[0]) };
        }""")
        print(res)
        ok = res['big'][0] == 'standSave:begin+share' and 'standShare:' not in res['big'] and res['big'].count('standSave:chunk') == 10 and res['big'][-1] == 'standSave:end' and res['small'] == ['standShare'] and not errs
        print('errors', errs[:3]); print('PASS' if ok else 'FAIL', 'a big file is shared in pieces, a small one as before')
        await b.close()
asyncio.run(main())
