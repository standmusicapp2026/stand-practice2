# A score whose cover picture can no longer be saved (as WebKit does with a Blob it lost: "Error
# preparing Blob/File data to be stored"): renamed in More › Title, then back to the library. The new
# title must stay under the cover, after starting again too; the cover is made anew.
import asyncio, os
from playwright.async_api import async_playwright
res = []
def ok(c, m): res.append(bool(c)); print('PASS' if c else 'FAIL', m, flush=True)
BREAK = r"""
(() => {
  const put0 = IDBObjectStore.prototype.put;
  IDBObjectStore.prototype.put = function (v, k) {
    if (window.__breakThumb && this.name === 'scores' && v && v.thumb && v.id === window.__breakThumb) throw new DOMException('Error preparing Blob/File data to be stored in object store', 'UnknownError');
    return put0.call(this, v, k);
  };
})();
"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)
        pg = await ctx.new_page(); await pg.add_init_script('window.__noTour = true;'); await pg.add_init_script(BREAK)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        base = 'http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'
        await pg.goto(base); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); setTimeout(() => document.querySelector('.tour-skip')?.click(), 300); }"); await pg.wait_for_timeout(700)
        await pg.set_input_files('#importInput', ['/home/claude/fixtures/vector8.pdf'])
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=60000)
        await pg.wait_for_timeout(2000)
        J = lambda js: pg.evaluate("async () => { const sleep=(ms)=>new Promise(r=>setTimeout(r,ms)); const { db } = await import('/js/db.js'); " + js + " }")
        sid = await J("const s = (await db.all('scores'))[0]; window.__breakThumb = s.id; return s.id;")
        await J("document.querySelector('#grid .card:not(.folder)').click(); await sleep(2500); document.querySelector('.tour-skip')?.click(); document.querySelector('#score [data-panel=settings]').click(); await sleep(400);")
        await pg.click('#metaTitle'); await pg.keyboard.press('Control+A'); await pg.keyboard.type('Beethoven Sonata Op. 69')
        await pg.wait_for_timeout(1000)
        await J("document.querySelector('#backBtn').click(); await sleep(2500);")
        card = await J("return document.querySelector('#grid .card:not(.folder) .ttl').textContent")
        rec = await J(f"const s = await db.get('scores', '{sid}'); return [s.title, !!s.thumb];")
        print('card', card, 'saved', rec)
        ok(card == 'Beethoven Sonata Op. 69' and rec[0] == 'Beethoven Sonata Op. 69', 'a score whose cover cannot be saved: the new title is kept and shown at home')
        await J("window.__breakThumb = null;")
        await pg.reload(); await pg.wait_for_timeout(4000)
        card2 = await J("return document.querySelector('#grid .card:not(.folder) .ttl').textContent")
        cover = await J(f"for (let i = 0; i < 40; i++) {{ const s = await db.get('scores', '{sid}'); if (s && s.thumb) return true; await sleep(250); }} return false;")
        ok(card2 == 'Beethoven Sonata Op. 69', 'after starting again: still the new title (' + card2 + ')')
        ok(cover, 'the cover is made anew by itself')
        print(errs[:3]); ok(not errs, 'no page errors')
        print('PASS' if all(res) else 'FAIL', 'title kept when the cover cannot be saved')
        await b.close()
asyncio.run(main())
