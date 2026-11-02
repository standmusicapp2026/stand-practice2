# The iPhone asks the iPad for pages of a heavy scan while the same scan is open on the stand:
# pages arrive, and the memory stays down (never two of its pages drawn at once)
import asyncio, os, sys, json, subprocess, threading, time
from playwright.async_api import async_playwright
PDF = sys.argv[1]
peak = [0]; stop = [False]
def rss():
    out = subprocess.run(['ps','-eo','rss,comm'], capture_output=True, text=True).stdout
    return sum(int(l.split()[0]) for l in out.splitlines()[1:] if 'chrom' in l or 'headless' in l) // 1024
def sampler():
    while not stop[0]: peak[0] = max(peak[0], rss()); time.sleep(0.05)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', PDF)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(4000)
        base = rss(); th = threading.Thread(target=sampler); th.start()
        r = await pg.evaluate("""async () => { const { db } = await import('/js/db.js'); const sc = (await db.all('scores'))[0]; const t0 = performance.now(); const out = [];
          const turns = (async () => { for (let k = 0; k < 4; k++) { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); await new Promise(r => setTimeout(r, 700)); } })().catch(() => {});
          for (let i = 10; i < 14; i++) { const a = await window.__answerPhone({ what: 'page', id: sc.id, i }); out.push([i, a.w, a.h, Math.round((a.img || '').length / 1024)]); }
          await turns; return { out, ms: Math.round(performance.now() - t0), page: document.querySelector('#pageLabel').textContent }; }""")
        stop[0] = True; th.join()
        print(json.dumps(r), 'peak extra MB', peak[0] - base)
        print(errs[:3]); await b.close()
asyncio.run(main())
