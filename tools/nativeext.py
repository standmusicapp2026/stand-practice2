# The newer iPad app's extras, with the app side mocked: the place reopened after the page stops,
# memory low, a backup saved straight into the Stand folder, background time asked for downloads
import asyncio, os, json
from playwright.async_api import async_playwright
MOCK = """window.standCaps = { native: true, files: 1, busy: 1, recover: 1 }; window.__saved = []; window.__busy = []; window.__keep = [];
const parts = {};
window.webkit = { messageHandlers: {
  standSave: { postMessage(m) { if (m.op === 'begin') parts[m.id] = { name: m.name, folder: m.folder, n: 0 }; else if (m.op === 'chunk') parts[m.id].n += atob(m.data).length; else if (m.op === 'end') { const p = parts[m.id]; window.__saved.push([p.folder, p.name, p.n]); setTimeout(() => window.standSaved({ id: m.id, ok: true, path: p.folder + '/' + p.name }), 30); } else if (m.op === 'keep') window.__keep.push(m); } },
  standBusy: { postMessage(m) { window.__busy.push(m); } },
} };"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820})
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;' + MOCK)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT','8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.evaluate("async () => { document.querySelector('#grid .card:not(.folder)').click(); await new Promise(r => setTimeout(r, 2500)); }")
        await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(600); await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(800)
        before = await pg.evaluate("() => document.querySelector('#pageLabel')?.textContent")
        await pg.evaluate("() => window.standMemoryLow()"); await pg.wait_for_timeout(300)
        await pg.goto(base + '?recover=1'); await pg.wait_for_timeout(4000)
        after = await pg.evaluate("() => [!document.querySelector('#score').hidden, document.querySelector('#pageLabel')?.textContent, location.search]")
        print('page before', before, 'after recover', after)
        # closing the score forgets the place: a normal start opens the library
        await pg.evaluate("() => document.querySelector('#backBtn').click()"); await pg.wait_for_timeout(800)
        await pg.goto(base + '?recover=1'); await pg.wait_for_timeout(3000)
        print('after closing, recover opens score:', await pg.evaluate("() => !document.querySelector('#score').hidden"))
        # a backup: saved straight into the folder
        r = await pg.evaluate("""async () => { const sleep = (ms) => new Promise(r => setTimeout(r, ms)); document.querySelector('.tile[data-panel=backup], [data-panel=backup]').click(); await sleep(500);
          document.querySelector('#bkMake').click(); for (let i = 0; i < 100 && !window.__saved.length; i++) await sleep(200); await sleep(1500);
          return { saved: window.__saved, keep: window.__keep.map(k => [k.prefix, k.count]), how: document.querySelector('#bkHow').textContent.slice(0, 60), btns: [...document.querySelectorAll('#bkList .btn')].map(x => x.textContent), busy: window.__busy }; }""")
        print(json.dumps(r, ensure_ascii=False))
        print('errors', errs[:4]); await b.close()
asyncio.run(main())
