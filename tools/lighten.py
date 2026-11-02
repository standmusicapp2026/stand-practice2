# A heavy scan opened in Stand: after its first pages, a light copy is made in the background;
# the pages then come from it (fast, little memory), and look right
import asyncio, os, sys, json, subprocess, base64
from playwright.async_api import async_playwright
PDF = sys.argv[1]
def rss():
    out = subprocess.run(['ps','-eo','rss,comm'], capture_output=True, text=True).stdout
    return sum(int(l.split()[0]) for l in out.splitlines()[1:] if 'chrom' in l or 'headless' in l) // 1024
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1180, 'height': 820})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT','8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => { document.querySelector('#welGo')?.click(); document.querySelector('.tour-skip')?.click(); }")
        await pg.set_input_files('#importInput', PDF)
        await pg.wait_for_function("document.querySelectorAll('#grid .card:not(.folder)').length >= 1", timeout=120000)
        await pg.evaluate("() => document.querySelector('#grid .card:not(.folder)').click()"); await pg.wait_for_timeout(5000)
        # let the light copy be made for a while
        n0 = await pg.evaluate("async () => { const P = await import('/js/pixcache.js'); const s = await import('/js/db.js'); const sc = (await s.db.all('scores'))[0]; const f = await s.db.get('files', sc.fileId); return [(await P.lightKeys(f.id + ':' + f.data.byteLength)).size, f.id + ':' + f.data.byteLength]; }")
        await pg.wait_for_timeout(int(os.environ.get('WAIT', '40000')))
        n1 = await pg.evaluate("async (fid) => { const P = await import('/js/pixcache.js'); return (await P.lightKeys(fid)).size; }", n0[1])
        # turning pages now: the time and memory
        base = rss(); peak = base; times = []
        for k in range(6):
            import time; t0 = time.time(); await pg.keyboard.press('ArrowRight')
            await pg.wait_for_function("() => { const c = document.querySelector('#stage .pg canvas.art'); return c && c.width > 10; }", timeout=20000)
            times.append(round((time.time() - t0) * 1000)); t = None
            peak = max(peak, rss()); await pg.wait_for_timeout(400); peak = max(peak, rss())
        print(json.dumps({'light_before': n0[0], 'light_after': n1, 'turns_ms': times, 'turn_peak_extra_MB': peak - base, 'page': await pg.evaluate("() => document.querySelector('#pageLabel').textContent")}))
        await pg.screenshot(path='/tmp/claude-0/-home-claude/03421858-f41d-50dc-b20d-e2cac84f0cae/scratchpad/light.png')
        print(errs[:4]); await b.close()
asyncio.run(main())
