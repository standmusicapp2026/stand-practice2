# Capture: turning through the pages of a score is immediate (the lines are found afterwards, in
# a thread of their own); the lines of the page you stop on are found
import asyncio, os, json, base64
from playwright.async_api import async_playwright
PDF = os.environ.get('PDF', '/home/claude/fixtures/imslp12.pdf')
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context(viewport={'width': 1366, 'height': 1024})).new_page()
        await pg.add_init_script('window.__noTour = true;'); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('http://localhost:' + os.environ.get('PORT', '8765') + '/index.html'); await pg.wait_for_timeout(1200)
        await pg.evaluate("() => document.querySelector('#welGo')?.click()")
        data = base64.b64encode(open(PDF, 'rb').read()).decode()
        r = await pg.evaluate("""async (b64) => {
          const P = await import('/js/picker.js'); const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
          const f = new File([bin], 'test.pdf', { type: 'application/pdf' });
          P.pickRegion('file', f, {}); const sleep = (ms) => new Promise(r => setTimeout(r, ms));
          for (let i = 0; i < 100 && !document.querySelector('#pkPageNo').textContent; i++) await sleep(100);
          await sleep(300);
          // ticks of the page's own thread while turning: it stays free
          let ticks = 0, maxGap = 0, last = performance.now(); const iv = setInterval(() => { const n = performance.now(); maxGap = Math.max(maxGap, n - last); last = n; ticks++; }, 16);
          const times = [];
          for (let k = 0; k < 5; k++) { const t0 = performance.now(); const want = 'Page ' + (k + 2); document.querySelector('#pkNext').click();
            for (let i = 0; i < 300 && !document.querySelector('#pkPageNo').textContent.startsWith(want); i++) await sleep(10);
            times.push(Math.round(performance.now() - t0)); await sleep(150); }
          const t1 = performance.now();
          for (let i = 0; i < 300 && !document.querySelector('#pkFinding').hidden; i++) await sleep(50);
          clearInterval(iv);
          return { pages: document.querySelector('#pkPageNo').textContent, turn_ms: times, mainMaxGapMs: Math.round(maxGap), linesFoundAfterMs: Math.round(performance.now() - t1), lines: document.querySelector('#pkAll').hidden ? 0 : 'yes' };
        }""", data)
        print(json.dumps(r)); print('errors', errs[:3]); await b.close()
asyncio.run(main())
